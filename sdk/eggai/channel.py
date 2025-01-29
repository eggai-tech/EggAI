from typing import (
    Dict, Any, Optional
)

from .stop import register_stop
from .transport.base import Transport, get_default_transport


class Channel:
    """
    A channel that publishes messages to a given 'name' on its own Transport.
    Default name is "eggai.channel".
    Lazy connection on first publish.
    """

    def __init__(self, name: str = "eggai.channel", transport: Optional[Transport] = None):
        """
        :param name: Channel (topic) name.
        :param transport: A concrete transport instance.
        """
        self.name = name
        self.transport = transport if transport is not None else get_default_transport()
        self._connected = False
        self._stop_registered = False

    async def _ensure_connected(self):
        if not self._connected:
            await self.transport.connect(group_id=None)  # publish-only
            self._connected = True
            # Auto-register stop
            if not self._stop_registered:
                register_stop(self.stop)
                self._stop_registered = True

    async def publish(self, message: Dict[str, Any]):
        """
        Lazy-connect on first publish
        """
        await self._ensure_connected()
        await self.transport.publish(self.name, message)

    async def stop(self):
        if self._connected:
            await self.transport.disconnect()
            self._connected = False
