import asyncio

from eggai import eggai_main
from eggai.transport import eggai_set_default_transport

from agents.triage.config import settings
from libraries.communication.transport import create_kafka_transport
from libraries.ml.dspy.language_model import dspy_set_language_model
from libraries.observability.logger import get_console_logger
from libraries.observability.tracing import init_telemetry
from libraries.observability.tracing.init_metrics import init_token_metrics

eggai_set_default_transport(
    lambda: create_kafka_transport(
        bootstrap_servers=settings.kafka_bootstrap_servers,
        ssl_cert=settings.kafka_ca_content,
    )
)
init_token_metrics(port=settings.prometheus_metrics_port, application_name=settings.app_name)

from agents.triage.agent import triage_agent

logger = get_console_logger("triage_agent")


@eggai_main
async def main():

    logger.info(f"Starting {settings.app_name}")

    init_telemetry(app_name=settings.app_name, endpoint=settings.otel_endpoint)
    logger.info(f"Telemetry initialized for {settings.app_name}")
    dspy_set_language_model(settings)

    await triage_agent.start()
    logger.info(f"{settings.app_name} started successfully")

    await asyncio.Future()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Shutting down triage agent")
    except Exception as e:
        logger.error(f"Error in main: {e}", exc_info=True)
