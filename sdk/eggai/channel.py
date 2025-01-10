import json
from aiokafka import AIOKafkaProducer

from sdk.eggai.constants import DEFAULT_CHANNEL_NAME
from sdk.eggai.settings.kafka import KafkaSettings


class Channel:
    """
    A class to interact with Kafka channels for event publishing.

    This class provides functionality to publish events to Kafka topics (channels)
    and manage Kafka producers efficiently using a singleton approach. It ensures
    each Kafka topic has a single producer instance for optimal resource usage.
    """

    _producers = {}

    def __init__(self, name: str = DEFAULT_CHANNEL_NAME):
        """
        Initialize the Channel instance.

        Args:
            name (str): The name of the Kafka topic (channel) to publish messages to.
                        Defaults to the `DEFAULT_CHANNEL_NAME` constant.
        """
        self.name = name
        self.kafka_settings = KafkaSettings()

    async def _get_producer(self) -> AIOKafkaProducer:
        """
        Get or create a Kafka producer for the current channel.

        This method uses a singleton pattern to ensure that each Kafka topic has
        a single producer instance.

        Returns:
            AIOKafkaProducer: The Kafka producer instance associated with the channel.
        """
        if self.name not in Channel._producers:
            producer = AIOKafkaProducer(
                bootstrap_servers=self.kafka_settings.BOOTSTRAP_SERVERS,
            )
            await producer.start()
            Channel._producers[self.name] = producer
        return Channel._producers[self.name]

    async def publish(self, event: dict):
        """
        Publish an event to the Kafka channel.

        This method serializes the event as JSON and sends it to the Kafka topic associated
        with the channel.

        Args:
            event (dict): The event data to publish. It must be JSON serializable.

        Example:
            channel = Channel(name="orders")
            await channel.publish({
                "event_name": "order_created",
                "payload": {"order_id": 123, "status": "created"}
            })
        """
        producer = await self._get_producer()
        await producer.send_and_wait(self.name, json.dumps(event).encode("utf-8"))

    @staticmethod
    async def stop():
        """
        Stop and close all Kafka producers managed by the Channel class.

        This method ensures that all active producers are properly closed, and
        the `_producers` dictionary is cleared to release resources.

        Example:
            await Channel.stop()
        """
        for producer in Channel._producers.values():
            await producer.stop()
        Channel._producers.clear()
