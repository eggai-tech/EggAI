import asyncio
import uuid
from collections import defaultdict
from typing import (
    List, Dict, Any, Optional, Callable, Tuple, Union
)

from .channel import Channel
from .transport.base import Transport
from .transport import get_default_transport
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
        self._default_group_id = name + "_group_" + uuid.uuid4().hex
        # Each entry is (channel_name, filter_func, handler, group_id)

        self._subscriptions: Dict[
            (str, str), List[Tuple[
                Callable[[Dict[str, Any]], bool], Union[
            Callable, "asyncio.Future"]]]] = {}

        self._started = False
        self._stop_registered = False

    def subscribe(
            self,
            channel: Optional[Channel] = None,
            filter_func: Callable[[Dict[str, Any]], bool] = lambda e: True,
            group_id: Optional[str] = None
    ):
        """
        Decorator for adding a subscription.
        If channel is None, we assume "eggai.channel".
        filter_func is optional, defaults to lambda e: True
        """
        channel_name = channel._name if channel else "eggai.channel"
        group_id = group_id or self._default_group_id

        def decorator(handler: Callable[[Dict[str, Any]], "asyncio.Future"]):
            if (channel_name, group_id) not in self._subscriptions:
                self._subscriptions[(channel_name, group_id)] = []
            self._subscriptions[(channel_name, group_id)].append((filter_func, handler))
            return handler

        return decorator

    async def start(self):
        if self._started:
            return

        if self._transport is None:
            self._transport = get_default_transport()

        await self._transport.connect()
        self._started = True

        if not self._stop_registered:
            await eggai_register_stop(self.stop)
            self._stop_registered = True

        for (ch_name, group_id), subscriptions in self._subscriptions.items():
            for filter_func, handler in subscriptions:
                async def wrapped_handler(event, h=handler, f=filter_func):
                    result = f(event)
                    if result:
                        await h(event)
                await self._transport.subscribe(ch_name, wrapped_handler, group_id)

    async def stop(self):
        if self._started:
            await self._transport.disconnect()
            self._started = False
