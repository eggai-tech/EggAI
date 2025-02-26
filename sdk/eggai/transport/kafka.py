import asyncio
import json
import uuid
from typing import Dict, Any, Optional, Callable, Tuple, List

import aiokafka

from eggai.transport.base import Transport


class CustomRebalanceListener(aiokafka.ConsumerRebalanceListener):
    
    def __init__(self, agent_name: str):
        self.agent_name = agent_name
        pass
    
    async def on_partitions_revoked(self, revoked: set):
        revoked_str = ', '.join([str(tp) for tp in revoked])
        print(len(revoked))
        print(f"{self.agent_name}: Partitions revoked: {revoked_str}")

    async def on_partitions_assigned(self, assigned):
        print(f"{self.agent_name}: Partitions assigned: {assigned}")

class KafkaTransport(Transport):
    def __init__(
            self,
            bootstrap_servers: str = "localhost:19092",
            auto_offset_reset: str = "latest",
            rebalance_timeout_ms: int = 1000,
            agent_name: str = "Agent"
    ):
        self.bootstrap_servers = bootstrap_servers
        self.auto_offset_reset = auto_offset_reset
        self.rebalance_timeout_ms = rebalance_timeout_ms
        self._name = agent_name

        self.producer: Optional[aiokafka.AIOKafkaProducer] = None
        # Mapping from (group_id, channel) to consumer instance
        self._consumers: Dict[Tuple[str, str], aiokafka.AIOKafkaConsumer] = {}
        # Mapping from (group_id, channel) to the consumer's asyncio task
        self._consume_tasks: Dict[Tuple[str, str], asyncio.Task] = {}
        # Mapping from (group_id, channel) to a list of subscription callbacks
        self._subscriptions: Dict[Tuple[str, str], List[Callable[[Dict[str, Any]], "asyncio.Future"]]] = {}

    async def connect(self):
        """Starts the Kafka producer."""
        if not self.producer:
            self.producer = aiokafka.AIOKafkaProducer(
                bootstrap_servers=self.bootstrap_servers
            )
            await self.producer.start()

    async def disconnect(self):
        """Stops all consumers, cancels tasks, and stops the producer."""
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
        """Publishes a message to a given channel (topic)."""
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
        """
        Subscribes to a channel (topic) with the provided group_id. A new consumer is
        created for each (group_id, channel) pair if one doesn't already exist, and
        multiple callbacks for the same subscription are supported.
        """
        key = (group_id, channel)
        if key not in self._subscriptions:
            self._subscriptions[key] = []
        self._subscriptions[key].append(callback)

        # If no consumer exists for this key, create one.
        if key not in self._consumers:
            consumer = aiokafka.AIOKafkaConsumer(
                channel,
                bootstrap_servers=self.bootstrap_servers,
                group_id=group_id,
                auto_offset_reset=self.auto_offset_reset,
                enable_auto_commit=False,
                rebalance_timeout_ms=10 * 1000,
                max_poll_records=1,
                max_poll_interval_ms=120 * 1000,
                heartbeat_interval_ms=3 * 1000,
                session_timeout_ms=10 * 1000,
                
            )
            consumer.subscribe([channel], listener=CustomRebalanceListener(self._name))
            await consumer.start()
            self._consumers[key] = consumer
            self._consume_tasks[key] = asyncio.create_task(self._consume_loop(key, consumer))

    async def _consume_loop(self, key: Tuple[str, str], consumer: aiokafka.AIOKafkaConsumer):
        import time
        batch = []
        last_flush_time = time.monotonic()
        try:
            while True:
                result = await consumer.getmany(timeout_ms=50, max_records=5)
                for tp, msgs in result.items():
                    for msg in msgs:
                        event = json.loads(msg.value.decode("utf-8"))
                        batch.append((tp, event, msg.offset))
                
                current_time = time.monotonic()
                if batch and (len(batch) >= 1):
                    events = [event for _, event, _ in batch.copy()]
                    await self._process_batch(key, events)
                    await consumer.commit({
                        tp: aiokafka.structs.OffsetAndMetadata(offset + 1, "") for tp, _, offset in batch
                    })
                    batch.clear()
                    last_flush_time = current_time
        except asyncio.CancelledError:
            if batch:
                events = [event for _, event, _ in batch]
                print(f"Flushing {len(events)} events for {key} in cancelled")
                await self._process_batch(key, events)
            raise
        except Exception as e:
            # print stack trace
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
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for result in results:
                if isinstance(result, Exception):
                    print(f"Error in callback for {key}: {result}")
