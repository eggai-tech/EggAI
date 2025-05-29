"""
Main module for the Escalation Agent.

This module contains the main entry point for the escalation agent.
It sets up the language model, transport, telemetry, and starts the agent.
"""

import asyncio
import logging

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

# Import agent after transport is configured
from .agent import ticketing_agent

# Configure logger
logger = get_console_logger("escalation_agent")
logger.setLevel(logging.INFO)


@eggai_main
async def main():
    """Main entry point for the escalation agent."""
    logger.info(f"Starting {settings.app_name}")

    # Initialize OpenTelemetry
    init_telemetry(app_name=settings.app_name)
    logger.info(f"Telemetry initialized for {settings.app_name}")

    # Configure language model
    dspy_set_language_model(settings)
    logger.info(f"Using language model: {settings.language_model}")

    # Start the agent
    await ticketing_agent.start()
    logger.info(f"{settings.app_name} started successfully")

    # Keep the agent running
    try:
        await asyncio.Future()
    except asyncio.CancelledError:
        logger.info("Escalation agent task cancelled")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Shutting down escalation agent")
    except Exception as e:
        logger.error(f"Error in main: {e}", exc_info=True)
