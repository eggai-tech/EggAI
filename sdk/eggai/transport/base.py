import asyncio
import sys
from abc import ABC, abstractmethod
from collections import defaultdict
from typing import (
    Dict, Any, Optional, Callable, List, Tuple
)

_DEFAULT_TRANSPORT_FACTORY: Optional[Callable[[], "Transport"]] = None


def eggai_set_default_transport(factory: Callable[[], "Transport"]):
    """
    Set a global function that returns a fresh Transport instance.
    Agents or Channels created without an explicit transport
    will use this factory.
    """
    global _DEFAULT_TRANSPORT_FACTORY
    _DEFAULT_TRANSPORT_FACTORY = factory


def get_default_transport() -> "Transport":
    """
    Get a fresh Transport instance from the default factory.
    If no default transport factory is set, return an InMemoryTransport instance and print a warning.
    """
    if _DEFAULT_TRANSPORT_FACTORY is None:
        print(
            "EggAI: Warning, no default transport factory set, InMemoryTransport will be used. Use eggai_set_default_transport() if you don't want see this warning.",
            file=sys.stderr)
        sys.stderr.flush()
        eggai_set_default_transport(lambda: InMemoryTransport())
    return _DEFAULT_TRANSPORT_FACTORY()


class Transport(ABC):
    """
    Abstract base for any transport. It should manage publishing,
    subscribing, connecting, and disconnecting.
    """

    @abstractmethod
    async def connect(self, group_id: Optional[str] = None):
        """
        Connect to the underlying system.
        If group_id is None, no consumer should be created (publish-only).
        """
        pass

    @abstractmethod
    async def disconnect(self):
        """
        Cleanly disconnect from the transport.
        """
        pass

    @abstractmethod
    async def publish(self, channel: str, message: Dict[str, Any]):
        """
        Publish the given message to the channel.
        """
        pass

    @abstractmethod
    async def subscribe(
            self, channel: str, callback: Callable[[Dict[str, Any]], "asyncio.Future"]
    ):
        """
        Subscribe to a channel with the given callback, invoked on new messages.
        (No-op if a consumer doesn’t exist.)
        """
        pass


class InMemoryTransport(Transport):
    # One queue per (channel, group_id). Each Agent sees its own queue.
    _CHANNELS: Dict[str, Dict[Optional[str], asyncio.Queue]] = defaultdict(dict)
    # For each channel and group_id, store a list of aggregator callbacks
    _SUBSCRIPTIONS: Dict[str, Dict[Optional[str], List[Callable]]] = defaultdict(
        lambda: defaultdict(list)
    )

    def __init__(self):
        self.group_id: Optional[str] = None
        self._connected = False
        # We'll keep references to the consume tasks keyed by (channel, group_id)
        self._consume_tasks: Dict[Tuple[str, Optional[str]], asyncio.Task] = {}

    async def connect(self, group_id: Optional[str] = None):
        self.group_id = group_id
        self._connected = True
        # If we have a group_id, we might start consume loops for any channels
        # that are already subscribed with this group_id.
        if self.group_id is not None:
            # For all channels that have aggregator callbacks for this group_id,
            # create a consume loop if not already present
            for channel, group_map in InMemoryTransport._SUBSCRIPTIONS.items():
                if self.group_id in group_map:
                    # There's at least 1 aggregator callback for (channel, group_id)
                    if (channel, self.group_id) not in self._consume_tasks:
                        self._consume_tasks[(channel, self.group_id)] = asyncio.create_task(
                            self._consume_loop(channel, self.group_id)
                        )

    async def disconnect(self):
        for task in self._consume_tasks.values():
            task.cancel()
        for task in self._consume_tasks.values():
            try:
                await task
            except asyncio.CancelledError:
                pass
        self._consume_tasks.clear()
        self._connected = False

    async def publish(self, channel: str, message: Dict[str, Any]):
        if not self._connected:
            raise RuntimeError("Transport not connected. Call `connect()` first.")
        # Put the message into *all* group queues for this channel
        # so each group sees the message
        if channel not in InMemoryTransport._CHANNELS:
            InMemoryTransport._CHANNELS[channel] = {}
        for grp_id, queue in InMemoryTransport._CHANNELS[channel].items():
            await queue.put(message)

    async def subscribe(
            self, channel: str, callback: Callable[[Dict[str, Any]], "asyncio.Future"]
    ):
        if self.group_id is None:
            # We can store the callback, but it won't get messages unless
            # group_id is set. Typically, we do a single aggregator for "publish-only"
            # but that doesn't do anything. We'll store it anyway.
            InMemoryTransport._SUBSCRIPTIONS[channel][None].append(callback)
            return

        # We have a group_id => consumer
        InMemoryTransport._SUBSCRIPTIONS[channel][self.group_id].append(callback)

        # Ensure queue for (channel, self.group_id)
        if self.group_id not in InMemoryTransport._CHANNELS[channel]:
            InMemoryTransport._CHANNELS[channel][self.group_id] = asyncio.Queue()

        # If we're connected and no consume task for (channel, group_id), start one
        if self._connected:
            key = (channel, self.group_id)
            if key not in self._consume_tasks:
                self._consume_tasks[key] = asyncio.create_task(
                    self._consume_loop(channel, self.group_id)
                )

    async def _consume_loop(self, channel: str, group_id: Optional[str]):
        queue = InMemoryTransport._CHANNELS[channel].get(group_id)
        if not queue:
            # Create if missing
            queue = asyncio.Queue()
            InMemoryTransport._CHANNELS[channel][group_id] = queue

        try:
            while True:
                msg = await queue.get()
                # For each aggregator callback for (channel, group_id), call it
                callbacks = InMemoryTransport._SUBSCRIPTIONS[channel].get(group_id, [])
                for cb in callbacks:
                    await cb(msg)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            print(f"InMemoryTransport consume loop error on channel={channel}, group={group_id}: {e}")
