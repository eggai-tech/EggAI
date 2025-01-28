# transport/base.py
from abc import ABC, abstractmethod
from typing import Callable, Set, Dict, Any

class BaseTransport(ABC):
    """
    An abstract interface for message transport backends,
    e.g., Kafka, ZeroMQ, RabbitMQ, etc.
    """

    @abstractmethod
    async def start(self, channels: Set[str], group_id: str = ""):
        """
        Initialize and start the transport (producers/consumers).
        The `channels` argument is a set of topics/queues/streams to subscribe to.
        `group_id` can be used by transport backends that need consumer group semantics.
        """
        pass

    @abstractmethod
    async def stop(self):
        """
        Stop the transport, closing any connections, producers, etc.
        """
        pass

    @abstractmethod
    async def produce(self, channel: str, message: Dict[str, Any]):
        """
        Publish (produce) a message to a given channel (topic/queue).
        """
        pass

    @abstractmethod
    async def consume(self, on_message: Callable[[str, Dict[str, Any]], None]):
        """
        Continuously consume messages from the subscribed channels and
        invoke `on_message(channel_name, message_dict)` whenever a new
        message arrives.
        This is typically a long-running operation that you run inside a task.
        """
        pass
