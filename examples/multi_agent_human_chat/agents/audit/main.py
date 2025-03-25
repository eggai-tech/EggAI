import asyncio
from eggai import eggai_main
from eggai.transport import eggai_set_default_transport, KafkaTransport
from libraries.tracing import init_telemetry
from libraries.logger import get_console_logger
from .config import settings
from .agent import audit_agent

logger = get_console_logger("audit_agent")

@eggai_main
async def main():
    logger.info(f"Starting {settings.app_name}")
    
    init_telemetry(app_name=settings.app_name)
    logger.info(f"Telemetry initialized for {settings.app_name}")
    
    await audit_agent.start()
    logger.info(f"{settings.app_name} started successfully")

    await asyncio.Future()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Shutting down audit agent")
    except Exception as e:
        logger.error(f"Error in main: {e}", exc_info=True)
