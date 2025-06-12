#!/usr/bin/env python3
"""Main entry point for the Policy Documentation Agent and its components."""

import asyncio
import signal
import sys
from typing import List

from agents.policies.config import settings as policies_settings
from agents.policy_documentation_agent.agent import policy_documentation_agent
from agents.policy_documentation_agent.components.augmenting_agent import (
    augmenting_agent,
)
from agents.policy_documentation_agent.components.generation_agent import (
    generation_agent,
)
from agents.policy_documentation_agent.components.retrieval_agent import retrieval_agent
from libraries.channels import clear_channels
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
            task = asyncio.create_task(agent.run(), name=f"{agent.name}_task")
            tasks.append(task)
            logger.info(f"Started {agent.name}")

        logger.info("All agents started successfully")

        # Wait for shutdown signal or task completion
        done, pending = await asyncio.wait(
            tasks + [asyncio.create_task(shutdown_event.wait())],
            return_when=asyncio.FIRST_COMPLETED,
        )

        # Cancel remaining tasks
        for task in pending:
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

        # Clear channels before starting
        await clear_channels()

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
