import asyncio
import uuid
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
        Initializes the Agent instance.

        Args:
            name (str): The name of the agent (used as an identifier).
            transport (Optional[Transport]): A concrete transport instance (e.g., KafkaTransport, InMemoryTransport).
                If None, defaults to InMemoryTransport.
        """
        self._name = name
        self._transport = transport
        self._default_group_id = name + "_group_" + uuid.uuid4().hex
        # Each entry is (channel_name, filter_func, handler, group_id)
        self._subscriptions: Dict[
            (str, str), List[Tuple[
                Callable[[Dict[str, Any]], bool], Union[
                    Callable, "asyncio.Future"
                ]
            ]]
        ] = {}

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

        Args:
            channel (Optional[Channel]): The channel to subscribe to. If None, defaults to "eggai.channel".
            filter_func (Callable[[Dict[str, Any]], bool]): A function to filter events. Defaults to a function that always returns True.
            group_id (Optional[str]): The consumer group ID. If None, a default group ID is generated.

        Returns:
            Callable: A decorator that registers the given handler for the subscription.
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
        """
        Starts the agent by connecting the transport and subscribing to all registered channels.

        If no transport is provided, a default transport is used. Also registers a stop hook if not already registered.
        """
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
        """
        Stops the agent by disconnecting the transport.
        """
        if self._started:
            await self._transport.disconnect()
            self._started = False
