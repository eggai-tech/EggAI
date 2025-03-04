import asyncio
from abc import ABC, abstractmethod
from typing import (
    Dict, Any, Optional, Callable, Union
)

from eggai.schemas import BaseMessage


class Transport(ABC):
    """
    Abstract base for any transport. It should manage publishing,
    subscribing, connecting, and disconnecting.
    """

    @abstractmethod
    async def connect(self):
        """
        Connect to the underlying system.
        """
        pass

    @abstractmethod
    async def disconnect(self):
        """
        Cleanly disconnect from the transport.
        """
        pass

    @abstractmethod
    async def publish(self, channel: str, message: Union[Dict[str, Any], BaseMessage]):
        """
        Publish the given message to the channel.
        """
        pass

    @abstractmethod
    async def subscribe(
            self, channel: str, callback: Callable[[Dict[str, Any]], "asyncio.Future"], group_id: str
    ):
        """
        Subscribe to a channel with the given callback, invoked on new messages.
        (No-op if a consumer doesn’t exist.)
        """
        pass


