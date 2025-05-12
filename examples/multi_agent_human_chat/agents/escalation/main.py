import asyncio
from eggai import eggai_main
from eggai.transport import eggai_set_default_transport, KafkaTransport

from libraries.dspy_set_language_model import dspy_set_language_model
from libraries.tracing import init_telemetry
from libraries.logger import get_console_logger
from .agent import ticketing_agent
from .config import settings

logger = get_console_logger("escalation_agent")


@eggai_main
async def main():
    logger.info(f"Starting {settings.app_name}")
    
    init_telemetry(app_name=settings.app_name)
    logger.info(f"Telemetry initialized for {settings.app_name}")
    
    dspy_set_language_model(settings)
    
    # Configure Kafka transport
    logger.info(f"Using Kafka transport with servers: {settings.kafka_bootstrap_servers}")
    
    def create_kafka_transport():
        return KafkaTransport(
            bootstrap_servers=settings.kafka_bootstrap_servers,
        )
    
    eggai_set_default_transport(create_kafka_transport)
    
    await ticketing_agent.start()
    logger.info(f"{settings.app_name} started successfully")

    await asyncio.Future()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Shutting down escalation agent")
    except Exception as e:
        logger.error(f"Error in main: {e}", exc_info=True)
