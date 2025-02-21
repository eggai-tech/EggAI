import asyncio
import json
from typing import (
    Dict, Any, Optional, Callable
)

import aiokafka

from eggai.transport.base import Transport


class KafkaTransport(Transport):
    def __init__(
            self,
            bootstrap_servers: str = "localhost:19092",
            auto_offset_reset: str = "latest",
            rebalance_timeout_ms: int = 1000
    ):
        self.bootstrap_servers = bootstrap_servers
        self.auto_offset_reset = auto_offset_reset
        self.rebalance_timeout_ms = rebalance_timeout_ms

        self.producer: Optional[aiokafka.AIOKafkaProducer] = None
        self.consumer: Optional[aiokafka.AIOKafkaConsumer] = None
        self._consume_task: Optional[asyncio.Task] = None

        # For each channel, we hold a single aggregator callback
        # Because the aggregator might handle multiple filters
        self._subscriptions: Dict[str, Callable[[Dict[str, Any]], "asyncio.Future"]] = {}

    async def connect(self, group_id: Optional[str] = None):
        if not self.producer:
            self.producer = aiokafka.AIOKafkaProducer(
                bootstrap_servers=self.bootstrap_servers
            )
            await self.producer.start()

        if group_id is not None and not self.consumer:
            self.consumer = aiokafka.AIOKafkaConsumer(
                bootstrap_servers=self.bootstrap_servers,
                group_id=group_id,
                auto_offset_reset=self.auto_offset_reset,
                rebalance_timeout_ms=self.rebalance_timeout_ms
            )
            await self.consumer.start()

            # If we already have subscriptions, subscribe
            if self._subscriptions:
                self.consumer.subscribe(list(self._subscriptions.keys()))
                if not self._consume_task:
                    self._consume_task = asyncio.create_task(self._consume_loop())

    async def disconnect(self):
        if self._consume_task:
            self._consume_task.cancel()
            try:
                await self._consume_task
            except asyncio.CancelledError:
                pass
            self._consume_task = None

        if self.consumer:
            await self.consumer.stop()
            self.consumer = None

        if self.producer:
            await self.producer.stop()
            self.producer = None

    async def publish(self, channel: str, message: Dict[str, Any]):
        if not self.producer:
            raise RuntimeError("Transport not connected. Call `connect()` first.")
        data = json.dumps(message).encode("utf-8")
        await self.producer.send_and_wait(channel, data)

    async def subscribe(
            self, channel: str, callback: Callable[[Dict[str, Any]], "asyncio.Future"]
    ):
        # We store exactly one aggregator callback per channel
        self._subscriptions[channel] = callback

        if self.consumer:
            self.consumer.subscribe(list(self._subscriptions.keys()))

        if self.consumer and not self._consume_task:
            self._consume_task = asyncio.create_task(self._consume_loop())

    async def _consume_loop(self):
        try:
            async for msg in self.consumer:
                channel = msg.topic
                event = json.loads(msg.value.decode("utf-8"))
                cb = self._subscriptions.get(channel)
                if cb:
                    if asyncio.iscoroutinefunction(cb):
                        await cb(event)
                    else:
                        cb(event)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            print(f"KafkaTransport consume loop error: {e}")
