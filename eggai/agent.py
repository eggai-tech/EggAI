import asyncio
import json
from typing import Dict, List, Callable, Optional

from aiokafka import AIOKafkaProducer, AIOKafkaConsumer

from eggai.channel import Channel
from eggai.constants import DEFAULT_CHANNEL_NAME
from eggai.settings.kafka import KafkaSettings


def _get_channel_name(channel: Optional[Channel], channel_name: Optional[str]) -> str:
    return channel.name if channel else channel_name or DEFAULT_CHANNEL_NAME


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
        self._producer = None
        self._consumer = None
        self._handlers: List[Dict[str, Callable]] = []  # List of handlers with filters
        self._channels = set()  # Tracks all subscribed channels
        self._running_task = None

    def subscribe(self, channel_name: str = DEFAULT_CHANNEL_NAME, channel: Channel = None, filter_func: Optional[Callable[[Dict], bool]] = None) -> Callable:
        """
        Decorator for subscribing to a channel and binding a handler with an optional filter function.

        Args:
            channel_name (str): The channel where the event occurs (default is DEFAULT_CHANNEL_NAME).
            channel (Channel): An instance of the Channel class to use for publishing messages.
            filter_func (Callable[[Dict], bool], optional): A filter function to determine whether to handle a message.

        Returns:
            Callable: A decorator for wrapping the handler function.

        Example:
            @agent.subscribe(channel_name="orders", filter_func=lambda msg: msg.get("event_name") == "order_created")
            async def handle_order_created(message):
                print(f"Order created: {message}")
        """
        def decorator(func: Callable):
            channel_name_to_use = _get_channel_name(channel, channel_name)
            self._handlers.append({"channel":channel_name_to_use , "filter": filter_func, "handler": func, "handler_name": func.__name__})
            self._channels.add(channel_name_to_use)  # Track the channel
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
                *self._channels,
                bootstrap_servers=self.kafka_settings.BOOTSTRAP_SERVERS,
                group_id=f"{self.name}_group",
                auto_offset_reset="latest",
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
                message = json.loads(msg.value.decode("utf-8"))
                # Check all handlers to see if any should process this message
                for handler_entry in self._handlers:
                    if handler_entry["channel"] == channel_name:
                        filter_func = handler_entry["filter"]
                        handler = handler_entry["handler"]
                        # Apply the filter function (if any) or process the message directly
                        if filter_func is None or filter_func(message):
                            try:
                                await handler(message)  # Pass the entire message
                            except Exception as e:
                                print(f"Failed to process message from {channel_name}: {e} {message} {handler_entry['handler_name']}")
        except asyncio.CancelledError:
            pass
        finally:
            await self._consumer.stop()

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
        self._running_task.cancel()
        try:
            await self._running_task
        except asyncio.CancelledError:
            pass
