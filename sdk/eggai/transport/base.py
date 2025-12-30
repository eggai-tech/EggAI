import asyncio
from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any

from pydantic import BaseModel


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
    async def publish(self, channel: str, message: dict[str, Any] | BaseModel):
        """
        Publish the given message to the channel.
        """
        pass

    @abstractmethod
    async def subscribe(
        self,
        channel: str,
        callback: Callable[[dict[str, Any]], "asyncio.Future"],
        **kwargs,
    ) -> Callable:
        """
        Subscribe to a channel with the given callback, invoked on new messages.
        (No-op if a consumer doesn't exist.)
        """
        pass

    async def ensure_topic(self, channel: str):  # noqa: B027
        """
        Ensure a topic/channel exists. Default is no-op.
        Override in transports that need explicit topic creation (e.g., Kafka).
        """
        pass
