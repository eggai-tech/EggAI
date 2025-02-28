import uuid
from typing import Dict, Any, Optional, Callable, Awaitable

from .hooks import eggai_register_stop
from .transport.base import Transport
from .transport import get_default_transport


class Channel:
    """
    A channel that publishes messages to a given 'name' on its own Transport.
    The default name is "eggai.channel".
    Connection is established lazily on the first publish or subscription.
    """

    def __init__(self, name: str = "eggai.channel", transport: Optional[Transport] = None):
        """
        Initialize a Channel instance.

        Args:
            name (str): The channel (topic) name. Defaults to "eggai.channel".
            transport (Optional[Transport]): A concrete transport instance. If None, a default transport is used.
        """
        self._name = name
        self._default_group_id = name + "_group_" + uuid.uuid4().hex
        self._transport = transport
        self._connected = False
        self._stop_registered = False

    async def _ensure_connected(self):
        """
        Ensure that the channel is connected by establishing a connection to the transport.
        If not already connected, it retrieves a default transport (if none provided) and connects.
        Also registers a stop hook on first connection.
        """
        if not self._connected:
            if self._transport is None:
                self._transport = get_default_transport()

            # Connect with group_id=None for publish-only by default.
            await self._transport.connect()
            self._connected = True
            # Auto-register stop hook if not already registered.
            if not self._stop_registered:
                await eggai_register_stop(self.stop)
                self._stop_registered = True

    async def publish(self, message: Dict[str, Any]):
        """
        Publish a message to the channel. Establishes a connection if not already connected.

        Args:
            message (Dict[str, Any]): The message payload to publish.
        """
        await self._ensure_connected()
        await self._transport.publish(self._name, message)

    async def subscribe(self, callback: Callable[[Dict[str, Any]], Awaitable[None]], group_id: Optional[str] = None):
        """
        Subscribe to the channel by registering a callback to be invoked when messages are received.

        Args:
            callback (Callable[[Dict[str, Any]], Awaitable[None]]): An asynchronous function that processes a message dictionary.
            group_id (Optional[str]): The consumer group ID to use. If None, a default group ID is generated.
        """
        await self._ensure_connected()
        await self._transport.subscribe(self._name, callback, group_id or self._default_group_id)

    async def stop(self):
        """
        Disconnects the channel's transport if connected.
        """
        if self._connected:
            await self._transport.disconnect()
            self._connected = False
