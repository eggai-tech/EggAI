"""Run the policies agent test harness."""

import asyncio

from agents.policies.agent.react import policies_react_dspy
from agents.policies.config import settings
from libraries.channels import clear_channels
from libraries.dspy_set_language_model import dspy_set_language_model
from libraries.logger import get_console_logger
from dspy import Prediction
from dspy.streaming import StreamResponse

logger = get_console_logger("policies_agent.test")


async def main() -> None:
    """Execute a simple streaming test for the policies agent."""
    dspy_set_language_model(settings)
    await clear_channels()

    test_conversation = (
        "User: I need information about my policy.\n"
        "PoliciesAgent: Sure, I can help with that. Could you please provide me with your policy number?\n"
        "User: My policy number is A12345\n"
    )

    logger.info("Running test query for policies agent")
    chunks = policies_react_dspy(chat_history=test_conversation)
    async for chunk in chunks:
        if isinstance(chunk, StreamResponse):
            logger.info("Chunk: %s", chunk.chunk)
        elif isinstance(chunk, Prediction):
            logger.info("Final response: %s", chunk.final_response)


if __name__ == "__main__":
    asyncio.run(main())
