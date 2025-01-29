import asyncio
import json
from typing import Set, Dict, Any, Awaitable, Callable

from aiokafka import AIOKafkaProducer, AIOKafkaConsumer

from .base import BaseTransport
from ..settings.kafka import KafkaSettings


class KafkaTransport(BaseTransport):
    def __init__(self, config: KafkaSettings = KafkaSettings(), auto_offset_reset: str = "latest"):
        self.bootstrap_servers = config.BOOTSTRAP_SERVERS
        self.auto_offset_reset = auto_offset_reset

        self._producer: AIOKafkaProducer = None
        self._consumer: AIOKafkaConsumer = None
        self._channels: Set[str] = set()
        self._consume_task = None
        self._running = False

    async def start(self, channels: Set[str], group_id: str = ""):
        """
        Start the Kafka producers/consumers for the given channels.
        """
        if self._running:
            return
        self._channels = channels
        # Initialize the producer
        self._producer = AIOKafkaProducer(bootstrap_servers=self.bootstrap_servers)
        await self._producer.start()

        # Initialize the consumer
        self._consumer = AIOKafkaConsumer(
            *self._channels,
            bootstrap_servers=self.bootstrap_servers,
            group_id=group_id or None,
            auto_offset_reset=self.auto_offset_reset,
        )
        await self._consumer.start()
        self._running = True

    async def stop(self):
        """
        Stop all Kafka producers and consumers.
        """
        self._running = False

        if self._consumer:
            await self._consumer.stop()
            self._consumer = None

        if self._producer:
            await self._producer.stop()
            self._producer = None

        if self._consume_task:
            self._consume_task.cancel()
            self._consume_task = None

    async def produce(self, channel: str, message: Dict[str, Any]):
        """
        Publish a message to Kafka.
        """
        if not self._producer:
            raise RuntimeError("KafkaTransport is not started or producer is missing.")
        await self._producer.send_and_wait(channel, json.dumps(message).encode("utf-8"))

    async def consume(self, on_message: Callable[[str, Dict[str, Any]], Awaitable]):
        """
        Continuously consume messages from Kafka and call on_message(channel, msg_dict).
        This method is designed to run inside a task (e.g., create_task).
        """
        if not self._consumer:
            raise RuntimeError("KafkaTransport is not started or consumer is missing.")

        try:
            async for msg in self._consumer:
                channel_name = msg.topic
                message = json.loads(msg.value.decode("utf-8"))
                await on_message(channel_name, message)
        except asyncio.CancelledError:
            pass
