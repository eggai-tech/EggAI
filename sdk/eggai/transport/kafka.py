import asyncio
import json
from typing import Dict, Any, Optional, Callable, Tuple, List

import aiokafka
from aiokafka.structs import TopicPartition, OffsetAndMetadata

from eggai.transport.base import Transport


class CustomRebalanceListener(aiokafka.ConsumerRebalanceListener):
    def __init__(self, consumer: aiokafka.AIOKafkaConsumer, offset_tracker: Dict[TopicPartition, int]):
        self.consumer = consumer
        self.offset_tracker = offset_tracker

    async def on_partitions_revoked(self, revoked: set):
        commit_offsets = {}
        for tp in revoked:
            if tp in self.offset_tracker:
                commit_offsets[tp] = OffsetAndMetadata(self.offset_tracker[tp] + 1, "")
        
        if commit_offsets:
            await self.consumer.commit(commit_offsets)

    async def on_partitions_assigned(self, assigned):
        pass

class KafkaTransport(Transport):
    def __init__(
            self,
            bootstrap_servers: str = "localhost:19092",
            auto_offset_reset: str = "latest",
            rebalance_timeout_ms: int = 1000,
            max_records_per_batch: int = 1,
            batch_timeout_ms: int = 300,
    ):
        self.bootstrap_servers = bootstrap_servers
        self.auto_offset_reset = auto_offset_reset
        self.rebalance_timeout_ms = rebalance_timeout_ms
        self.max_records_per_batch = max_records_per_batch
        if self.max_records_per_batch < 1:
            raise ValueError("max_records_per_batch must be at least 1.")
        self.batch_timeout_ms = batch_timeout_ms

        self.producer: Optional[aiokafka.AIOKafkaProducer] = None
        self._consumers: Dict[Tuple[str, str], aiokafka.AIOKafkaConsumer] = {}
        self._consume_tasks: Dict[Tuple[str, str], asyncio.Task] = {}
        self._subscriptions: Dict[Tuple[str, str], List[Callable[[Dict[str, Any]], "asyncio.Future"]]] = {}

    async def connect(self):
        if not self.producer:
            self.producer = aiokafka.AIOKafkaProducer(bootstrap_servers=self.bootstrap_servers)
            await self.producer.start()

    async def disconnect(self):
        for task in self._consume_tasks.values():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        self._consume_tasks.clear()

        for consumer in self._consumers.values():
            await consumer.stop()
        self._consumers.clear()

        if self.producer:
            await self.producer.stop()
            self.producer = None

    async def publish(self, channel: str, message: Dict[str, Any]):
        if not self.producer:
            raise RuntimeError("Transport not connected. Call `connect()` first.")
        data = json.dumps(message).encode("utf-8")
        await self.producer.send_and_wait(channel, data)

    async def subscribe(
            self,
            channel: str,
            callback: Callable[[Dict[str, Any]], "asyncio.Future"],
            group_id: str
    ):
        key = (group_id, channel)
        if key not in self._subscriptions:
            self._subscriptions[key] = []
        self._subscriptions[key].append(callback)

        if key not in self._consumers:
            offset_tracker: Dict[TopicPartition, int] = {}

            consumer = aiokafka.AIOKafkaConsumer(
                channel,
                bootstrap_servers=self.bootstrap_servers,
                group_id=group_id,
                auto_offset_reset=self.auto_offset_reset,
                enable_auto_commit=False,
                rebalance_timeout_ms=10 * 1000,
                max_poll_records=self.max_records_per_batch,
                max_poll_interval_ms=120 * 1000,
                heartbeat_interval_ms=3 * 1000,
                session_timeout_ms=10 * 1000,
            )
            # Pass both the consumer and the tracker to the listener.
            listener = CustomRebalanceListener(consumer, offset_tracker)
            consumer.subscribe([channel], listener=listener)
            await consumer.start()
            self._consumers[key] = consumer
            self._consume_tasks[key] = asyncio.create_task(self._consume_loop(key, consumer, offset_tracker))

    async def _consume_loop(self, key: Tuple[str, str], consumer: aiokafka.AIOKafkaConsumer, offset_tracker: Dict[TopicPartition, int]):
        import time
        batch = []
        last_flush_time = time.monotonic()
        try:
            while True:
                result = await consumer.getmany(timeout_ms=50, max_records=self.max_records_per_batch)
                for tp, msgs in result.items():
                    for msg in msgs:
                        event = json.loads(msg.value.decode("utf-8"))
                        batch.append((tp, event, msg.offset))
                        offset_tracker[tp] = msg.offset

                current_time = time.monotonic()
                if batch and (len(batch) >= self.max_records_per_batch or current_time - last_flush_time >= 0.3):
                    events = [event for _, event, _ in batch.copy()]
                    await self._process_batch(key, events)
                    commit_dict = {
                        tp: OffsetAndMetadata(offset + 1, "")
                        for tp, _, offset in batch
                    }
                    await consumer.commit(commit_dict)
                    batch.clear()
                    last_flush_time = current_time
        except asyncio.CancelledError:
            if batch:
                events = [event for _, event, _ in batch]
                print(f"Flushing {len(events)} events for {key} in cancelled")
                await self._process_batch(key, events)
                commit_dict = {
                    tp: OffsetAndMetadata(offset + 1, "")
                    for tp, _, offset in batch
                }
                await consumer.commit(commit_dict)
                batch.clear()
            raise
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"KafkaTransport consume loop error for {key}: {e}")

    async def _process_batch(self, key: Tuple[str, str], events: List[Dict[str, Any]]):
        tasks = []
        for event in events:
            callbacks = self._subscriptions.get(key, [])
            for cb in callbacks:
                if asyncio.iscoroutinefunction(cb):
                    tasks.append(asyncio.create_task(cb(event)))
                else:
                    loop = asyncio.get_running_loop()
                    tasks.append(loop.run_in_executor(None, cb, event))
        if tasks:
            # don't wait for results, just log errors
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for result in results:
                if isinstance(result, Exception):
                    print(f"Error in callback for {key}: {result}")
