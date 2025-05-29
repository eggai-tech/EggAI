import ssl
from typing import Optional

from eggai.transport import KafkaTransport
from faststream.kafka import KafkaBroker
from faststream.security import BaseSecurity


def create_kafka_transport(
    bootstrap_servers: str, ssl_cert: Optional[str] = None
) -> KafkaTransport:
    """
    Create a KafkaTransport instance with SSL support when certificate is provided.

    Args:
        bootstrap_servers: Comma-separated list of Kafka bootstrap servers
        ssl_cert: SSL certificate content as a string (optional)

    Returns:
        KafkaTransport: Configured Kafka transport instance
    """
    # Parse bootstrap servers
    servers_list = bootstrap_servers.split(",")

    # Use SSL if certificate is provided
    if ssl_cert and ssl_cert.strip():
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE

        # Load the certificate directly from the string
        ssl_context.load_verify_locations(cadata=ssl_cert)

        # Create broker with SSL
        broker = KafkaBroker(
            bootstrap_servers=servers_list,
            security=BaseSecurity(use_ssl=True, ssl_context=ssl_context),
        )
    else:
        # Create broker without SSL
        broker = KafkaBroker(bootstrap_servers=servers_list)

    return KafkaTransport(broker=broker)
