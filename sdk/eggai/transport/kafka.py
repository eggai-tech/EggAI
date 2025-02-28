import asyncio
import enum
import json
import uuid
import time
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

class KafkaTransportProcessingGuarantee(enum.Enum):
    AT_LEAST_ONCE = "at_least_once"
    EXACTLY_ONCE = "exactly_once"    

class KafkaTransport(Transport):
    def __init__(
        self,
        bootstrap_servers: str = "localhost:19092",
        auto_offset_reset: str = "latest",
        rebalance_timeout_ms: int = 1000,
        max_records_per_batch: int = 1,
        batch_timeout_ms: int = 300,
        processing_guarantee: KafkaTransportProcessingGuarantee = KafkaTransportProcessingGuarantee.AT_LEAST_ONCE,
    ):
        """_summary_

        Args:
            bootstrap_servers (_type_, optional): _description_. Defaults to "localhost:19092".
            auto_offset_reset (str, optional): _description_. Defaults to "latest".
            rebalance_timeout_ms (int, optional): _description_. Defaults to 1000.
            max_records_per_batch (int, optional): _description_. Defaults to 1.
            batch_timeout_ms (int, optional): _description_. Defaults to 300.
            processing_guarantee (KafkaTransportProcessingGuarantee, optional): _description_. Defaults to AT_LEAST_ONCE.

        Raises:
            ValueError: _description_
            ValueError: _description_
        """
        self.processing_guarantee = processing_guarantee

        self.bootstrap_servers = bootstrap_servers
        self.auto_offset_reset = auto_offset_reset
        self.rebalance_timeout_ms = rebalance_timeout_ms
        self.max_records_per_batch = max_records_per_batch
        if self.max_records_per_batch < 1:
            raise ValueError("max_records_per_batch must be at least 1.")
        self.batch_timeout_ms = batch_timeout_ms
        self.batch_timeout_sec = self.batch_timeout_ms / 1000.0  # Convert ms to seconds

        self.producer: Optional[aiokafka.AIOKafkaProducer] = None
        self._consumers: Dict[Tuple[str, str], aiokafka.AIOKafkaConsumer] = {}
        self._consume_tasks: Dict[Tuple[str, str], asyncio.Task] = {}
        self._subscriptions: Dict[Tuple[str, str], List[Callable[[Dict[str, Any]], "asyncio.Future"]]] = {}

        # Lock for transactional operations if exactly-once is enabled.
        self._producer_lock: Optional[asyncio.Lock] = None

    async def connect(self):
        if not self.producer:
            if self.processing_guarantee == KafkaTransportProcessingGuarantee.EXACTLY_ONCE:
                transactional_id = f"kafka_transport_{uuid.uuid4()}"
                self.producer = aiokafka.AIOKafkaProducer(
                    bootstrap_servers=self.bootstrap_servers,
                    transactional_id=transactional_id,
                )
            else:
                self.producer = aiokafka.AIOKafkaProducer(bootstrap_servers=self.bootstrap_servers)
            await self.producer.start()
            if self.processing_guarantee == KafkaTransportProcessingGuarantee.EXACTLY_ONCE:
                self._producer_lock = asyncio.Lock()

    async def disconnect(self):
        # Cancel consumer tasks.
        for task in self._consume_tasks.values():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        self._consume_tasks.clear()

        # Stop all consumers.
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
        if self.processing_guarantee == KafkaTransportProcessingGuarantee.EXACTLY_ONCE:
            async with self._producer_lock:
                await self.producer.begin_transaction()
                try:
                    await self.producer.send_and_wait(channel, data)
                    await self.producer.commit_transaction()
                except Exception as e:
                    await self.producer.abort_transaction()
                    raise e
        else:
            await self.producer.send_and_wait(channel, data)

    async def subscribe(
        self,
        channel: str,
        callback: Callable[[Dict[str, Any]], "asyncio.Future"],
        group_id: str,
    ):
        key = (group_id, channel)
        self._subscriptions.setdefault(key, []).append(callback)

        if key not in self._consumers:
            offset_tracker: Dict[TopicPartition, int] = {}
            consumer_config = dict(
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
            # For exactly-once, only read committed messages.
            consumer_config["isolation_level"] = "read_committed" if self.processing_guarantee == KafkaTransportProcessingGuarantee.EXACTLY_ONCE else "read_uncommitted"

            consumer = aiokafka.AIOKafkaConsumer(channel, **consumer_config)
            listener = CustomRebalanceListener(consumer, offset_tracker)
            consumer.subscribe([channel], listener=listener)
            await consumer.start()
            self._consumers[key] = consumer
            self._consume_tasks[key] = asyncio.create_task(self._consume_loop(key, consumer, offset_tracker))

    async def _consume_loop(self, key: Tuple[str, str], consumer: aiokafka.AIOKafkaConsumer, offset_tracker: Dict[TopicPartition, int]):
        batch = []
        last_flush_time = time.monotonic()
        group_id, _ = key

        try:
            while True:
                result = await consumer.getmany(timeout_ms=50, max_records=self.max_records_per_batch)
                for tp, msgs in result.items():
                    for msg in msgs:
                        event = json.loads(msg.value.decode("utf-8"))
                        batch.append((tp, event, msg.offset))
                        offset_tracker[tp] = msg.offset

                current_time = time.monotonic()
                if batch and (len(batch) >= self.max_records_per_batch or current_time - last_flush_time >= self.batch_timeout_sec):
                    # Try to flush the batch; on failure (exactly-once), do not clear the batch for retry.
                    if await self._flush_batch(key, consumer, batch, group_id):
                        batch.clear()
                        last_flush_time = current_time
                    else:
                        continue

        except asyncio.CancelledError:
            if batch:
                events = [event for _, event, _ in batch]
                print(f"Flushing {len(events)} events for {key} on cancellation")
                try:
                    await self._flush_batch(key, consumer, batch, group_id)
                except Exception as e:
                    print(f"Error flushing batch for {key} on cancellation: {e}")
                batch.clear()
            raise
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"KafkaTransport consume loop error for {key}: {e}")

    def _get_commit_dict(self, consumer: aiokafka.AIOKafkaConsumer, batch: List[Tuple[TopicPartition, Any, int]]) -> Dict[TopicPartition, OffsetAndMetadata]:
        assigned = consumer.assignment()
        return {
            tp: OffsetAndMetadata(offset + 1, "")
            for tp, _, offset in batch
            if tp in assigned
        }

    async def _flush_batch(
        self,
        key: Tuple[str, str],
        consumer: aiokafka.AIOKafkaConsumer,
        batch: List[Tuple[TopicPartition, Any, int]],
        group_id: str,
    ) -> bool:
        """
        Process a batch of messages and commit offsets.
        Returns True if flush succeeded (so the batch can be cleared),
        or False if an error occurred in exactly-once processing (so the batch should be retried).
        """
        events = [event for _, event, _ in batch]
        if self.processing_guarantee == KafkaTransportProcessingGuarantee.EXACTLY_ONCE:
            try:
                async with self._producer_lock:
                    await self.producer.begin_transaction()
                    await self._process_batch(key, events)
                    commit_dict = self._get_commit_dict(consumer, batch)
                    if commit_dict:
                        await self.producer.send_offsets_to_transaction(commit_dict, group_id)
                    await self.producer.commit_transaction()
                return True
            except Exception as e:
                print(f"Error in processing batch for exactly_once guarantee for {key}: {e}")
                try:
                    async with self._producer_lock:
                        await self.producer.abort_transaction()
                except Exception as abort_e:
                    print(f"Error aborting transaction: {abort_e}")
                return False
        else:
            await self._process_batch(key, events)
            commit_dict = self._get_commit_dict(consumer, batch)
            if commit_dict:
                await consumer.commit(commit_dict)
            return True

    async def _process_batch(self, key: Tuple[str, str], events: List[Dict[str, Any]]):
        """
        Process events using the callbacks registered under the given key.
        Errors are printed but do not stop processing of other events.
        """
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
            async def _gather():
                results = await asyncio.gather(*tasks, return_exceptions=True)
                for result in results:
                    if isinstance(result, Exception):
                        print(f"Error in callback for {key}: {result}")
            asyncio.ensure_future(_gather())
