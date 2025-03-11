import asyncio
from typing import Dict, Any, Optional, Callable, Awaitable, Union

from pydantic import BaseModel

from .hooks import eggai_register_stop
from .transport import get_default_transport
from .transport.base import Transport


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
        if transport is None:
            self._transport = get_default_transport()
        else:
            self._transport = transport
        self._connected = False
        self._stop_registered = False

    def get_name(self) -> str:
        """
        Get the channel name.

        Returns:
            str: The channel name.
        """
        return self._name

    async def _ensure_connected(self):
        if not self._connected:
            await self._transport.connect()
            self._connected = True
            if not self._stop_registered:
                await eggai_register_stop(self.stop)
                self._stop_registered = True

    async def publish(self, message: Union[Dict[str, Any], BaseModel]):
        """
        Publish a message to the channel. Establishes a connection if not already connected.

        Args:
            message (Dict[str, Any]): The message payload to publish.
        """
        await self._ensure_connected()
        await self._transport.publish(self._name, message)

    async def subscribe(self, callback: Callable[[Dict[str, Any]], "asyncio.Future"]):
        """
        Subscribe to the channel by registering a callback to be invoked when messages are received.

        Args:
            callback (Callable[[Dict[str, Any]], "asyncio.Future"]): The callback to invoke on new messages.
        """
        await self._transport.subscribe(self._name, callback)
        await self._ensure_connected()



    async def stop(self):
        """
        Disconnects the channel's transport if connected.
        """
        if self._connected:
            await self._transport.disconnect()
            self._connected = False
