#!/usr/bin/env python3
"""Main entry point for the RAG Evaluation Agent."""

import asyncio
import signal
import sys

from eggai.transport import KafkaTransport, eggai_set_default_transport

from agents.rag_evaluation_agent.agent import rag_evaluation_agent, get_log_file_path, get_log_stats
from libraries.channels import clear_channels
from libraries.logger import get_console_logger
from libraries.tracing import init_telemetry

logger = get_console_logger("rag_evaluation_agent.main")

# Global flag for graceful shutdown
shutdown_event = asyncio.Event()


def signal_handler(signum, frame):
    """Handle shutdown signals gracefully."""
    logger.info(f"Received signal {signum}, initiating graceful shutdown...")
    shutdown_event.set()


async def main():
    """Main entry point for RAG Evaluation Agent."""
    try:
        # Set up signal handlers
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        # Initialize transport and telemetry
        eggai_set_default_transport(lambda: KafkaTransport())
        init_telemetry("RagEvaluationAgent")

        # Clear channels before starting
        await clear_channels()

        logger.info("Starting RAG Evaluation Agent...")
        logger.info(f"Logging to: {get_log_file_path()}")

        # Start the agent
        agent_task = asyncio.create_task(rag_evaluation_agent.start(), name="rag_evaluation_agent_task")
        
        logger.info("RAG Evaluation Agent started successfully")

        # Wait for shutdown signal or task completion
        done, pending = await asyncio.wait(
            [agent_task, asyncio.create_task(shutdown_event.wait())],
            return_when=asyncio.FIRST_COMPLETED,
        )

        # Cancel remaining tasks
        for task in pending:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        logger.info("RAG Evaluation Agent stopped")
        
        # Print final log statistics
        stats = get_log_stats()
        logger.info(f"Final log statistics: {stats}")

    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
    except Exception as e:
        logger.error(f"Fatal error in RAG Evaluation Agent: {e}", exc_info=True)
        sys.exit(1)
    finally:
        logger.info("RAG Evaluation Agent shutdown complete")


if __name__ == "__main__":
    asyncio.run(main())