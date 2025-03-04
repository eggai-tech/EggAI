import asyncio
import json
import uuid
from collections import defaultdict
from typing import Dict, Optional, List, Callable, Tuple, Any, Union

from eggai.schemas import BaseMessage
from eggai.transport import Transport


class InMemoryTransport(Transport):
    # One queue per (channel, group_id). Each consumer group gets its own queue.
    _CHANNELS: Dict[str, Dict[str, asyncio.Queue]] = defaultdict(dict)
    # For each channel and group_id, store a list of subscription callbacks.
    _SUBSCRIPTIONS: Dict[str, Dict[str, List[Callable[[Dict[str, Any]], "asyncio.Future"]]]] = defaultdict(
        lambda: defaultdict(list)
    )

    def __init__(self):
        self._connected = False
        # Keep references to consume tasks keyed by (channel, group_id)
        self._consume_tasks: Dict[Tuple[str, str], asyncio.Task] = {}

    async def connect(self):
        """Marks the transport as connected and starts consume loops for existing subscriptions."""
        self._connected = True
        # Start consume loops for all existing subscriptions.
        for channel, group_map in InMemoryTransport._SUBSCRIPTIONS.items():
            for group_id in group_map.keys():
                key = (channel, group_id)
                if key not in self._consume_tasks:
                    self._consume_tasks[key] = asyncio.create_task(self._consume_loop(channel, group_id))

    async def disconnect(self):
        """Cancels all consume loops and marks the transport as disconnected."""
        for task in self._consume_tasks.values():
            task.cancel()
        for task in self._consume_tasks.values():
            try:
                await task
            except asyncio.CancelledError:
                pass
        self._consume_tasks.clear()
        self._connected = False

    async def publish(self, channel: str, message: Union[Dict[str, Any], BaseMessage]):
        """
        Publishes a message to the given channel.
        The message is put into all queues for that channel so each consumer group receives it.
        """
        if not self._connected:
            raise RuntimeError("Transport not connected. Call `connect()` first.")
        if channel not in InMemoryTransport._CHANNELS:
            InMemoryTransport._CHANNELS[channel] = {}

        if hasattr(message, "model_dump_json"):
            data = message.model_dump_json()
        else:
            data = json.dumps(message)

        for grp_id, queue in InMemoryTransport._CHANNELS[channel].items():
            await queue.put(data)

    async def subscribe(
            self,
            channel: str,
            callback: Callable[[Dict[str, Any]], "asyncio.Future"],
            group_id: Optional[str] = None
    ):
        """
        Subscribes to a channel with the provided group_id.
        If no group_id is given, a unique one is generated, ensuring that each subscription
        gets its own consumer (broadcast mode).
        """
        if not group_id:
            group_id = uuid.uuid4().hex
        key = (group_id, channel)
        # Store the callback for this (channel, group_id) pair.
        InMemoryTransport._SUBSCRIPTIONS[channel][group_id].append(callback)
        # Ensure a queue exists for this (channel, group_id).
        if group_id not in InMemoryTransport._CHANNELS[channel]:
            InMemoryTransport._CHANNELS[channel][group_id] = asyncio.Queue()
        # Start a consume loop for this subscription if not already started.
        if self._connected and key not in self._consume_tasks:
            self._consume_tasks[key] = asyncio.create_task(self._consume_loop(channel, group_id))

    async def _consume_loop(self, channel: str, group_id: str):
        """
        Continuously pulls messages from the queue for (channel, group_id)
        and dispatches them to all registered callbacks.
        """
        queue = InMemoryTransport._CHANNELS[channel].get(group_id)
        if not queue:
            queue = asyncio.Queue()
            InMemoryTransport._CHANNELS[channel][group_id] = queue

        try:
            while True:
                msg = await queue.get()
                data = json.loads(msg)
                callbacks = InMemoryTransport._SUBSCRIPTIONS[channel].get(group_id, [])
                for cb in callbacks:
                    await cb(data)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            print(f"InMemoryTransport consume loop error on channel={channel}, group={group_id}: {e}")
