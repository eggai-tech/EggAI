import asyncio

from eggai import eggai_main
from eggai.transport import eggai_set_default_transport

from libraries.dspy_set_language_model import dspy_set_language_model
from libraries.kafka_transport import create_kafka_transport
from libraries.logger import get_console_logger
from libraries.tracing import init_telemetry

from .config import settings

eggai_set_default_transport(
    lambda: create_kafka_transport(
        bootstrap_servers=settings.kafka_bootstrap_servers,
        ssl_cert=settings.kafka_ca_content,
    )
)

from .agent import billing_agent

logger = get_console_logger("billing_agent")


@eggai_main
async def main():
    logger.info(f"Starting {settings.app_name}")

    init_telemetry(app_name=settings.app_name, endpoint=settings.otel_endpoint)
    dspy_set_language_model(settings)

    await billing_agent.start()
    logger.info(f"{settings.app_name} started successfully")

    await asyncio.Future()



if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Shutting down billing agent")
    except Exception as e:
        logger.error(f"Error in main: {e}", exc_info=True)
