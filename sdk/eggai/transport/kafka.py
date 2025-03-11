import json
import logging
from typing import Dict, Any, Optional, Callable, Union

from faststream.kafka import KafkaBroker, KafkaMessage

from eggai.schemas import BaseMessage
from eggai.transport.base import Transport


class KafkaTransport(Transport):
    """
    Kafka-based transport layer adapted to use FastStream's KafkaBroker for message publishing and consumption.
    """

    def __init__(self, broker: Optional[KafkaBroker] = None, bootstrap_servers: str = "localhost:19092", **kwargs):
        if broker:
            self.broker = broker
        else:
            self.broker = KafkaBroker(bootstrap_servers, log_level=logging.DEBUG, **kwargs)

    async def connect(self):
        await self.broker.start()

    async def disconnect(self):
        await self.broker.close()

    async def publish(self, channel: str, message: Union[Dict[str, Any], BaseMessage]):
        await self.broker.publish(message, topic=channel)

    async def subscribe(self, channel: str, handler, **kwargs) -> Callable:
        if "filter_func" in kwargs:
            filter_func = kwargs.pop("filter_func")
            def filter_by_payload(message: KafkaMessage):
                return filter_func(json.loads(message.body.decode("utf-8")))
            kwargs["filter"] = filter_by_payload
        return self.broker.subscriber(channel, **kwargs)(handler)
