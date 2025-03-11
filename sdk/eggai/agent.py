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
        self._subscriptions: List[Tuple[str, Callable[[Dict[str, Any]], "asyncio.Future"], Dict]] = []
        self._started = False
        self._stop_registered = False

    def subscribe(self, channel: Optional[Channel] = None, **kwargs):
        """
        Decorator for adding a subscription.

        Args:
            channel (Optional[Channel]): The channel to subscribe to. If None, defaults to "eggai.channel".

        Returns:
            Callable: A decorator that registers the given handler for the subscription.
        """

        def decorator(handler: Callable[[Dict[str, Any]], "asyncio.Future"]):
            channel_name = channel.get_name() if channel else "eggai.channel"
            self._subscriptions.append((channel_name, handler, kwargs))
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

        for (channel, handler, kwargs) in self._subscriptions:
            await self._transport.subscribe(channel, handler, **kwargs)

        await self._transport.connect()
        self._started = True

        if not self._stop_registered:
            await eggai_register_stop(self.stop)
            self._stop_registered = True



    async def stop(self):
        """
        Stops the agent by disconnecting the transport.
        """
        if self._started:
            await self._transport.disconnect()
            self._started = False
