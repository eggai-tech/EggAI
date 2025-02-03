import asyncio
from collections import defaultdict
from typing import (
    List, Dict, Any, Optional, Callable, Tuple
)

from .channel import Channel
from .transport.base import Transport, get_default_transport
from .hooks import eggai_register_stop


class Agent:
    """
    A message-based agent for subscribing to events and handling messages
    with user-defined functions.
    """

    def __init__(self, name: str, transport: Optional[Transport] = None):
        """
        :param name: The name of the agent (used as an identifier).
        :param transport: A concrete transport instance (KafkaTransport, InMemoryTransport, etc.).
                          If None, defaults to InMemoryTransport.
        """
        self._name = name
        self._transport = transport
        # Each entry is (channel_name, filter_func, handler)
        self._subscriptions: List[Tuple[str, Callable[[Dict[str, Any]], bool], Callable]] = []

        self._started = False
        self._stop_registered = False

    def subscribe(
            self,
            channel: Optional[Channel] = None,
            filter_func: Callable[[Dict[str, Any]], bool] = lambda e: True
    ):
        """
        Decorator for adding a subscription.
        If channel is None, we assume "eggai.channel".
        filter_func is optional, defaults to lambda e: True
        """
        channel_name = channel._name if channel else "eggai.channel"

        def decorator(handler: Callable[[Dict[str, Any]], "asyncio.Future"]):
            self._subscriptions.append((channel_name, filter_func, handler))
            return handler

        return decorator

    async def start(self):
        if self._started:
            return

        if self._transport is None:
            self._transport = get_default_transport()

        # Connect with group_id=self.name for consumption
        await self._transport.connect(group_id=self._name)
        self._started = True

        if not self._stop_registered:
            await eggai_register_stop(self.stop)
            self._stop_registered = True

        # Group this agent's subscriptions by channel name
        subs_by_name: Dict[str, List[Tuple[Callable[[Dict[str, Any]], bool], Callable]]] = defaultdict(list)
        for ch_name, f_func, h_func in self._subscriptions:
            subs_by_name[ch_name].append((f_func, h_func))

        # For each distinct channel name, create a single aggregator callback
        # that merges all the filters/handlers for *this agent*.
        for ch_name, subs in subs_by_name.items():
            async def aggregator(event: Dict[str, Any], local_subs=subs):
                for fil, handler in local_subs:
                    if fil(event):
                        await handler(event)

            # Subscribe our aggregator to the transport
            await self._transport.subscribe(ch_name, aggregator)

    async def stop(self):
        if self._started:
            await self._transport.disconnect()
            self._started = False
