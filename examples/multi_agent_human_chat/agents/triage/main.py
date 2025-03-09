import asyncio
import dspy
from eggai import eggai_main
from eggai.transport import eggai_set_default_transport, KafkaTransport
from libraries.tracing import init_telemetry
from libraries.logger import get_console_logger
from .agent import triage_agent
from .config import settings

logger = get_console_logger("triage_agent")


@eggai_main
async def main():
    logger.info(f"Starting {settings.app_name}")
    
    init_telemetry(app_name=settings.app_name)
    logger.info(f"Telemetry initialized for {settings.app_name}")
    
    language_model = dspy.LM(settings.language_model, cache=settings.cache_enabled)
    logger.info(f"Configured language model: {settings.language_model}")
    
    dspy.configure(lm=language_model)
    
    # Configure Kafka transport
    logger.info(f"Using Kafka transport with servers: {settings.kafka_bootstrap_servers}")
    
    def create_kafka_transport():
        return KafkaTransport(
            bootstrap_servers=settings.kafka_bootstrap_servers,
            rebalance_timeout_ms=settings.kafka_rebalance_timeout_ms
        )
    
    eggai_set_default_transport(create_kafka_transport)
    
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
