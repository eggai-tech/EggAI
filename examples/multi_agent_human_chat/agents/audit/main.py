import asyncio
import logging

from eggai import eggai_main
from eggai.transport import eggai_set_default_transport

from libraries.communication.transport import create_kafka_transport
from libraries.observability.logger import get_console_logger
from libraries.observability.tracing import init_telemetry

from .config import settings

eggai_set_default_transport(
    lambda: create_kafka_transport(
        bootstrap_servers=settings.kafka_bootstrap_servers,
        ssl_cert=settings.kafka_ca_content,
    )
)

from .agent import audit_agent

logger = get_console_logger("audit_agent")
logger.setLevel(logging.INFO)


@eggai_main
async def main():
    logger.info(f"Starting {settings.app_name}")

    init_telemetry(app_name=settings.app_name, endpoint=settings.otel_endpoint)
    logger.info(f"Telemetry initialized for {settings.app_name}")

    logger.info(
        f"Using Kafka transport with servers: {settings.kafka_bootstrap_servers}"
    )

    await audit_agent.start()
    logger.info(f"{settings.app_name} started successfully")

    try:
        await asyncio.Future()
    except asyncio.CancelledError:
        logger.info("Audit agent task cancelled")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Shutting down audit agent")
    except Exception as e:
        logger.error(f"Error in main: {e}", exc_info=True)
