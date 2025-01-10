import os
from dataclasses import dataclass


@dataclass
class KafkaSettings:
    BOOTSTRAP_SERVERS: str = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:19092")
    USE_SSL: bool = os.getenv("KAFKA_USE_SSL", False)
    CA_CONTENT: str | None = os.getenv("KAFKA_CA_CONTENT", None)
