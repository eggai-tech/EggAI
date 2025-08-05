"""
Simple EggAI Agent Demo - Shows A2A-enabled agent with text-based skills.

This demo shows how to create an EggAI agent with A2A support for text processing.
"""

import asyncio
import logging

from eggai import Agent, Channel, eggai_main, A2AConfig
from eggai.schemas import BaseMessage

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Define BaseMessage types for text
# A2A sends {"text": "value"} for TextPart, so we need to handle that
from typing import Union, Dict

class TextMessage(BaseMessage[Union[str, Dict[str, str]]]):
    type: str = "text.message"


# Simple A2A-enabled agent with text processing skills
async def create_simple_agent():
    """Create a simple agent with text-based A2A skills."""

    # A2A configuration
    a2a_config = A2AConfig(
        agent_name="TextAgent",
        description="A simple agent that can greet users and reverse text",
        version="1.0.0",
        base_url="http://localhost:8080",
    )

    # Create agent with A2A config
    agent = Agent("TextAgent", a2a_config=a2a_config)

    # Skill 1: Greeter
    @agent.subscribe(
        channel=Channel("greetings"), data_type=TextMessage, a2a_capability="greet"
    )
    async def greet(message: TextMessage) -> str:
        """Greet a user by name."""
        # Handle both plain string and {"text": "string"} format from A2A
        if isinstance(message.data, dict) and "text" in message.data:
            name = message.data["text"].strip()
        else:
            name = str(message.data).strip()
        
        # Create personalized greeting
        if name.lower() == "world":
            greeting = "Hello, World! Welcome to EggAI!"
        elif len(name) > 20:
            greeting = f"Wow, {name}, that's quite a long name! Nice to meet you!"
        else:
            greeting = f"Hello, {name}! How are you doing today?"
        
        logger.info(f"Greeted: {name}")
        return greeting

    # Skill 2: Text reverser
    @agent.subscribe(
        channel=Channel("text_ops"), data_type=TextMessage, a2a_capability="reverse"
    )
    async def reverse(message: TextMessage) -> str:
        """Reverse the input text."""
        # Handle both plain string and {"text": "string"} format from A2A
        if isinstance(message.data, dict) and "text" in message.data:
            text = message.data["text"]
        else:
            text = str(message.data)
        
        # Reverse the text
        reversed_text = text[::-1]
        
        logger.info(f"Reversed text: '{text}' -> '{reversed_text}'")
        return reversed_text

    # Skill 3: Text analyzer
    @agent.subscribe(
        channel=Channel("analysis"), data_type=TextMessage, a2a_capability="analyze"
    )
    async def analyze(message: TextMessage) -> str:
        """Analyze text and return statistics."""
        # Handle both plain string and {"text": "string"} format from A2A
        if isinstance(message.data, dict) and "text" in message.data:
            text = message.data["text"]
        else:
            text = str(message.data)
        
        # Perform simple analysis
        word_count = len(text.split())
        char_count = len(text)
        char_no_spaces = len(text.replace(" ", ""))
        
        analysis = (
            f"Text analysis:\n"
            f"- Characters: {char_count}\n"
            f"- Characters (no spaces): {char_no_spaces}\n"
            f"- Words: {word_count}\n"
            f"- Average word length: {char_no_spaces/max(word_count, 1):.1f}"
        )
        
        logger.info(f"Analyzed text with {word_count} words")
        return analysis

    # Start the agent
    await agent.start()
    logger.info("Text agent created with 3 skills: greet, reverse, analyze")

    return agent


@eggai_main
async def main():
    """Main demo function."""
    print("=== Simple EggAI A2A Text Demo ===")

    # Create and start the agent
    agent = await create_simple_agent()

    print(
        f"Agent created with {len(agent.plugins['a2a']['_instance'].skills)} A2A skills:"
    )
    for skill_name in agent.plugins["a2a"]["_instance"].skills.keys():
        print(f"  - {skill_name}")

    print("\nAgent ready. To run client test, use:")
    print("  python client.py")
    print("\nStarting A2A server on http://localhost:8080...")

    # Start A2A server
    await agent.to_a2a(host="0.0.0.0", port=8080)


if __name__ == "__main__":
    asyncio.run(main())