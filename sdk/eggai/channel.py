from eggai.constants import DEFAULT_CHANNEL_NAME
from eggai.settings.kafka import KafkaSettings
from eggai.transport.base import BaseTransport
from eggai.transport.kafka import KafkaTransport


class Channel:
    """
    A class to interact with Kafka channels for event publishing.
    """

    def __init__(
            self,
            name: str = DEFAULT_CHANNEL_NAME,
            transport: BaseTransport = None,
            kafka_settings: KafkaSettings = None
    ):
        """
        :param name: Channel (topic) name.
        :param transport: A concrete transport instance. If None, defaults to Kafka.
        :param kafka_settings: Optional if default Kafka is used.
        """
        self.name = name
        self.transport = transport or KafkaTransport(
            bootstrap_servers=(kafka_settings or KafkaSettings()).BOOTSTRAP_SERVERS
        )
        self._started = False

    async def start(self):
        """
        Some backends need to be explicitly started before producing.
        For KafkaTransport, we need to call `transport.start` with at least one channel.
        For ZeroMQTransport (PUB only), you may or may not need to call it.
        """
        if not self._started:
            # We pass an empty group_id for pure publishing (no consumer).
            await self.transport.start(channels=set([self.name]), group_id="")
            self._started = True

    async def publish(self, event: dict):
        if not self._started:
            await self.start()
        await self.transport.produce(self.name, event)

    async def stop(self):
        if self._started:
            await self.transport.stop()
            self._started = False
