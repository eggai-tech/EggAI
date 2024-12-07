import asyncio
import json
from typing import Dict, List, Callable

from aiokafka import AIOKafkaProducer, AIOKafkaConsumer

from eggai.constants import DEFAULT_CHANNEL_NAME
from eggai.settings.kafka import KafkaSettings

class Agent:
    """
    A message-based agent for subscribing to events and handling messages with user-defined functions.

    This class acts as an intermediary for message-based communication, allowing users to
    subscribe to specific event names on particular channels and handle incoming messages
    through custom callback functions. It uses Kafka as the messaging backend.
    """

    def __init__(self, name: str):
        """
        Initialize the Agent with a unique name.

        Args:
            name (str): The name of the agent, used as an identifier for the consumer group.
        """
        self.name = name
        self.kafka_settings = KafkaSettings()
        self._producer = None  # Kafka producer instance
        self._consumer = None  # Kafka consumer instance
        self._handlers: Dict[str, List[Callable]] = {}  # Maps channel:event_name to list of handlers
        self._channels = set()  # Tracks all subscribed channels
        self._running_task = None  # Task to manage the lifecycle of the agent

    def subscribe(self, event_name: str, channel_name: str = DEFAULT_CHANNEL_NAME) -> Callable:
        """
        Decorator for subscribing to a channel and binding a handler to a specific event.

        Allows users to define handler functions that are triggered when messages for the
        specified event name are received on the channel.

        Args:
            event_name (str): The name of the event to subscribe to.
            channel_name (str): The channel where the event occurs (default is DEFAULT_CHANNEL_NAME).

        Returns:
            Callable: A decorator for wrapping the handler function.

        Example:
            @agent.subscribe(event_name="order_created", channel_name="orders")
            async def handle_order_created(payload):
                print(f"Order created: {payload}")
        """
        def decorator(func: Callable):
            topic_event = f"{channel_name}:{event_name}"
            if topic_event not in self._handlers:
                self._handlers[topic_event] = []
            self._handlers[topic_event].append(func)  # Register the handler
            self._channels.add(channel_name)  # Track the channel
            return func
        return decorator

    async def _start_producer(self):
        """
        Initialize and start the Kafka producer.

        This producer is responsible for sending messages to Kafka topics. It is initialized
        with the bootstrap servers specified in the Kafka settings.
        """
        if self._producer is None:
            self._producer = AIOKafkaProducer(
                bootstrap_servers=self.kafka_settings.BOOTSTRAP_SERVERS
            )
            await self._producer.start()

    async def _start_consumer(self):
        """
        Initialize and start the Kafka consumer.

        This consumer listens to all subscribed channels and processes messages asynchronously.
        """
        if self._consumer is None:
            self._consumer = AIOKafkaConsumer(
                *self._channels,  # Subscribe to all tracked channels
                bootstrap_servers=self.kafka_settings.BOOTSTRAP_SERVERS,
                group_id=f"{self.name}_group",  # Consumer group for this agent
                auto_offset_reset="latest",  # Start from the latest messages
            )
            await self._consumer.start()

    async def _handle_messages(self):
        """
        Asynchronously handle incoming messages from Kafka topics.

        This method continuously listens for messages from the subscribed channels, parses them,
        and invokes the appropriate handlers based on the event name.

        Raises:
            asyncio.CancelledError: When the task is cancelled during shutdown.
        """
        try:
            async for msg in self._consumer:
                channel_name = msg.topic
                try:
                    message = json.loads(msg.value.decode("utf-8"))
                    event_name = message.get("event_name")
                    payload = message.get("payload")

                    topic_event = f"{channel_name}:{event_name}"
                    if topic_event in self._handlers:
                        # Invoke all handlers for the event
                        for handler in self._handlers[topic_event]:
                            await handler(payload)
                except Exception as e:
                    print(f"Failed to process message from {channel_name}: {e}")
        except asyncio.CancelledError:
            # Task cancelled during shutdown
            pass
        finally:
            print(f"Stopping agent '{self.name}'...")
            await self._consumer.stop()
            print(f"Agent '{self.name}' stopped.")

    async def run(self):
        """
        Start the agent by initializing the Kafka producer and consumer, and begin handling messages.

        This method sets up the necessary components and starts the main task for processing
        incoming messages.

        Raises:
            RuntimeError: If the agent is already running.
        """
        if self._running_task:
            raise RuntimeError("Agent is already running.")
        await self._start_producer()
        await self._start_consumer()
        self._running_task = asyncio.create_task(self._handle_messages())

    async def stop(self):
        """
        Stop the agent gracefully by cancelling the running task and stopping the producer.

        Ensures that all resources (e.g., producer and consumer) are cleaned up before the agent exits.

        Raises:
            RuntimeError: If the agent is not currently running.
        """
        if not self._running_task:
            raise RuntimeError("Agent is not running.")
        await self._producer.stop()
        self._running_task.cancel()  # Cancel the main processing task
        try:
            await self._running_task  # Wait for the task to finish
        except asyncio.CancelledError:
            # Ignore cancellation errors during shutdown
            pass
