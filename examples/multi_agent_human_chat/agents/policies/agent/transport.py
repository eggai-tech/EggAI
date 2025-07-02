from eggai.transport import eggai_set_default_transport

from agents.policies.config import settings
from libraries.kafka_transport import create_kafka_transport


def configure_transport() -> None:
    """Configure Kafka transport for the Policies agent."""

    eggai_set_default_transport(
        lambda: create_kafka_transport(
            bootstrap_servers=settings.kafka_bootstrap_servers,
            ssl_cert=settings.kafka_ca_content,
        )
    )
