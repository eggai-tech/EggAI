"""
Simple EggAI Agent Demo - Shows A2A-enabled agent with 2 skills.

This demo shows how to create an EggAI agent with A2A support using minimal code changes.
"""

import asyncio
import logging
from pydantic import BaseModel

from eggai import Agent, Channel, eggai_main, A2AConfig
from eggai.schemas import BaseMessage

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Define our data models
class GreetingRequest(BaseModel):
    name: str
    language: str = "en"

class GreetingResponse(BaseModel):
    message: str
    language: str

class MathRequest(BaseModel):
    operation: str  # "add", "multiply", "subtract", "divide"
    a: float
    b: float

class MathResponse(BaseModel):
    result: float
    operation: str

# Define BaseMessage types with specific types
class GreetingMessage(BaseMessage[GreetingRequest]):
    type: str = "greet.request"

class MathMessage(BaseMessage[MathRequest]):
    type: str = "calculate.request"

# Simple A2A-enabled agent with 2 skills
async def create_simple_agent():
    """Create a simple agent with 2 A2A skills."""
    
    # A2A configuration
    a2a_config = A2AConfig(
        agent_name="SimpleAgent",
        description="A simple agent that can greet users and do basic math",
        version="1.0.0",
        base_url="http://localhost:8080"
    )
    
    # Create agent with A2A config
    agent = Agent("SimpleAgent", a2a_config=a2a_config)
    
    # Skill 1: Greeting
    @agent.subscribe(
        channel=Channel("greetings"),
        data_type=GreetingMessage,
        a2a_capability="greet"
    )
    async def greet(message: GreetingMessage) -> GreetingResponse:
        """Greet a user in their preferred language."""
        data = message.data
        
        # Simple greeting logic
        greetings = {
            "en": f"Hello {data.name}! Nice to meet you.",
            "es": f"¡Hola {data.name}! Mucho gusto.",
            "fr": f"Bonjour {data.name}! Enchanté.",
        }
        
        greeting = greetings.get(data.language, greetings["en"])
        
        result = GreetingResponse(
            message=greeting,
            language=data.language
        )
        
        logger.info(f"Greeted {data.name} in {data.language}")
        return result
    
    # Skill 2: Math operations
    @agent.subscribe(
        channel=Channel("math"),
        data_type=MathMessage,
        a2a_capability="calculate"
    )
    async def calculate(message: MathMessage) -> MathResponse:
        """Perform basic math operations."""
        data = message.data
        
        # Simple math operations
        if data.operation == "add":
            result = data.a + data.b
        elif data.operation == "subtract":
            result = data.a - data.b
        elif data.operation == "multiply":
            result = data.a * data.b
        elif data.operation == "divide":
            if data.b == 0:
                raise ValueError("Cannot divide by zero")
            result = data.a / data.b
        else:
            raise ValueError(f"Unknown operation: {data.operation}")
        
        response = MathResponse(
            result=result,
            operation=data.operation
        )
        
        logger.info(f"Calculated {data.a} {data.operation} {data.b} = {result}")
        return response
    
    # Start the agent
    await agent.start()
    logger.info("Simple agent created with 2 skills: greet, calculate")
    
    return agent

@eggai_main
async def main():
    """Main demo function."""
    print("=== Simple EggAI A2A Demo ===")
    
    # Create and start the agent
    agent = await create_simple_agent()
    
    print(f"Agent created with {len(agent.plugins['a2a']['_instance'].skills)} A2A skills:")
    for skill_name in agent.plugins['a2a']['_instance'].skills.keys():
        print(f"  - {skill_name}")
    
    print("\nAgent ready. To run client test, use:")
    print("  python -m eggai.a2a_integration.demo.client")
    print("\nStarting A2A server on http://localhost:8080...")
    
    # Start A2A server (uncomment to enable server)
    await agent.to_a2a(host="0.0.0.0", port=8080)

if __name__ == "__main__":
    asyncio.run(main())