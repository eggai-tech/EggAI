"""Run the billing agent test harness."""

import asyncio

from agents.billing.agent import billing_optimized_dspy
from agents.billing.config import settings
from libraries.channels import clear_channels
from libraries.dspy_set_language_model import dspy_set_language_model
from libraries.logger import get_console_logger
from dspy import Prediction
from dspy.streaming import StreamResponse

logger = get_console_logger("billing_agent.test")


async def main() -> None:
    """Execute a simple streaming test for the billing agent."""
    dspy_set_language_model(settings)
    await clear_channels()

    test_conversation = (
        "User: How much is my premium?\n"
        "BillingAgent: Could you please provide your policy number?\n"
        "User: It's B67890.\n"
    )

    logger.info("Running test query for billing agent")
    chunks = billing_optimized_dspy(chat_history=test_conversation)
    async for chunk in chunks:
        if isinstance(chunk, StreamResponse):
            logger.info("Chunk: %s", chunk.chunk)
        elif isinstance(chunk, Prediction):
            logger.info("Final response: %s", chunk.final_response)


if __name__ == "__main__":
    asyncio.run(main())
