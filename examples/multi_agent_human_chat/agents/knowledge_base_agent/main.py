#!/usr/bin/env python3
"""Main entry point for the Policy Documentation Agent and its components."""

import asyncio
import signal
import sys
from typing import List

from eggai.transport import eggai_set_default_transport
from agents.policies.config import settings as policies_settings
from libraries.kafka_transport import create_kafka_transport

# Configure transport before importing agents
eggai_set_default_transport(
    lambda: create_kafka_transport(
        bootstrap_servers=policies_settings.kafka_bootstrap_servers,
        ssl_cert=policies_settings.kafka_ca_content,
    )
)

from agents.knowledge_base_agent.agent import policy_documentation_agent
from agents.knowledge_base_agent.components.augmenting_agent import (
    augmenting_agent,
)
from agents.knowledge_base_agent.components.generation_agent import (
    generation_agent,
)
from agents.knowledge_base_agent.components.retrieval_agent import retrieval_agent
from libraries.dspy_set_language_model import dspy_set_language_model
from libraries.logger import get_console_logger

logger = get_console_logger("policy_documentation_agent.main")

# Global flag for graceful shutdown
shutdown_event = asyncio.Event()


def signal_handler(signum, frame):
    """Handle shutdown signals gracefully."""
    logger.info(f"Received signal {signum}, initiating graceful shutdown...")
    shutdown_event.set()


async def initialize_agents() -> List:
    """Initialize all agent components."""
    logger.info("Initializing Policy Documentation Agent components...")

    # Set up the language model
    dspy_set_language_model(policies_settings)

    # Initialize components in order
    agents = [
        retrieval_agent,
        augmenting_agent,
        generation_agent,
        policy_documentation_agent,
    ]

    logger.info("All components initialized successfully")
    return agents


async def run_agents(agents: List):
    """Run all agent components concurrently."""
    logger.info("Starting Policy Documentation Agent system...")

    try:
        # Create tasks for all agents
        tasks = []

        for agent in agents:
            agent_name = getattr(agent, '_name', 'unknown_agent')
            task = asyncio.create_task(agent.start(), name=f"{agent_name}_task")
            tasks.append(task)
            logger.info(f"Started {agent_name}")

        logger.info("All agents started successfully")

        # Wait for shutdown signal only (let tasks run indefinitely)
        await shutdown_event.wait()
        
        # Cancel all tasks on shutdown
        for task in tasks:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        logger.info("All agents stopped")

    except Exception as e:
        logger.error(f"Error running agents: {e}", exc_info=True)
        raise


async def main():
    """Main entry point."""
    try:
        # Set up signal handlers
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        # Initialize and run agents
        agents = await initialize_agents()
        await run_agents(agents)

    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
    except Exception as e:
        logger.error(f"Fatal error in main: {e}", exc_info=True)
        sys.exit(1)
    finally:
        logger.info("Policy Documentation Agent system shutdown complete")


if __name__ == "__main__":
    asyncio.run(main())
