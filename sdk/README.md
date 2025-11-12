# EggAI SDK

EggAI Multi-Agent Meta Framework is an async-first framework for building, deploying, and scaling multi-agent systems for modern enterprise environments.

## Features

- **Multi-Transport Support**: Redis Streams (with consumer groups), Kafka, and more
- **Async-First**: Built on asyncio for high-performance concurrent processing
- **Type-Safe**: Full type hints and Pydantic validation
- **Production-Ready**: Comprehensive error handling, logging, and monitoring
- **Flexible Architecture**: Easily extensible with custom transports and middleware

## Installation

```bash
pip install eggai
```

Redis Streams and Kafka support are included by default.

Optional extras:
```bash
pip install eggai[cli]    # CLI tools for scaffolding
pip install eggai[a2a]     # A2A (Agent-to-Agent) SDK integration
pip install eggai[mcp]     # MCP (Model Context Protocol) support
```

## Quick Start

```python
from eggai import Agent, Channel
from eggai.transport.redis import RedisTransport

# Create a transport
transport = RedisTransport(url="redis://localhost:6379")

# Create channels
input_channel = Channel("input-channel", transport=transport)
output_channel = Channel("output-channel", transport=transport)

# Create an agent
agent = Agent(
    name="my-agent",
    input_channel=input_channel,
    output_channel=output_channel
)

# Define message handler
@agent.on_message
async def handle_message(message):
    # Process message
    result = await process(message)
    await output_channel.publish(result)

# Start the agent
await agent.start()
```

## Documentation

For full documentation, visit: https://eggai-tech.github.io/EggAI/

## License

MIT License - see LICENSE file for details
