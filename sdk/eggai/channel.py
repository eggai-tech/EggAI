from typing import Dict

from eggai.transport.zeromq import ZeroMQTransport
from eggai.constants import DEFAULT_CHANNEL_NAME
from eggai.transport.base import BaseTransport


class Channel:
    """
    A class to interact with Kafka channels for event publishing.
    """

    _channels: Dict[str, "Channel"] = {}

    def __new__(
        cls,
        name: str = DEFAULT_CHANNEL_NAME,
        transport: BaseTransport = None,
    ):
        if name in cls._channels:
            return cls._channels[name]

        instance = super().__new__(cls)
        cls._channels[name] = instance
        return instance

    def __init__(
        self,
        name: str = DEFAULT_CHANNEL_NAME,
        transport: BaseTransport = None,
    ):
        """
        :param name: Channel (topic) name.
        :param transport: A concrete transport instance. If None, defaults to 0MQ.
        """
        # Only initialize if not already initialized
        if not hasattr(self, "_initialized"):
            self.name = name
            self.transport = transport or ZeroMQTransport()
            self._started = False
            self._initialized = True

    async def _start(self):
        if not self._started:
            await self.transport.start(channels={self.name}, group_id="")
            self._started = True

    async def publish(self, event: dict):
        if not self._started:
            await self._start()
        await self.transport.produce(self.name, event)

    async def stop(self):
        if self._started:
            await self.transport.stop()
            self._started = False

    async def consume(self, on_message):
        if not self._started:
            await self._start()
        await self.transport.consume(on_message)
