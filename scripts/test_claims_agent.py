"""Run the claims agent test harness."""

import asyncio

from agents.claims.agent import claims_optimized_dspy
from agents.claims.config import settings
from libraries.channels import clear_channels
from libraries.dspy_set_language_model import dspy_set_language_model
from libraries.logger import get_console_logger
from dspy import Prediction
from dspy.streaming import StreamResponse

logger = get_console_logger("claims_agent.test")


async def main() -> None:
    """Execute a simple streaming test for the claims agent."""
    dspy_set_language_model(settings)
    await clear_channels()

    test_conversation = (
        "User: Hi, I'd like to file a new claim.\n"
        "ClaimsAgent: Certainly! Could you provide your policy number and incident details?\n"
        "User: Policy A12345, my car was hit at a stop sign.\n"
    )

    logger.info("Running test query for claims agent")
    chunks = claims_optimized_dspy(chat_history=test_conversation)
    async for chunk in chunks:
        if isinstance(chunk, StreamResponse):
            logger.info("Chunk: %s", chunk.chunk)
        elif isinstance(chunk, Prediction):
            logger.info("Final response: %s", chunk.final_response)


if __name__ == "__main__":
    asyncio.run(main())
