# EggAI SDK

EggAI Multi-Agent Meta Framework is an async-first framework for building, deploying, and scaling multi-agent systems for modern enterprise environments.

<img src="https://raw.githubusercontent.com/eggai-tech/EggAI/refs/heads/main/docs/docs/assets/eggai-meta-framework-arch.png" alt="EggAI Meta Framework Architecture" width="100%">

## Features

- **Multi-Transport Support**: In-Memory, Redis Streams, Kafka, and extensible for custom transports
- **Async-First**: Built on asyncio for high-performance concurrent processing
- **Type-Safe**: Full type hints and Pydantic validation with CloudEvents-compliant message protocol
- **Production-Ready**: Comprehensive error handling, logging, and monitoring
- **Flexible Architecture**: Easily extensible with custom transports and middleware
- **Protocol Interoperability**: A2A for agent collaboration, MCP for LLM tools, CloudEvents for messaging

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

### Using In-Memory Transport (Testing & Development)

Perfect for unit tests, prototyping, and local development.

```python
from eggai import Agent, Channel, InMemoryTransport

# Create an in-memory transport
transport = InMemoryTransport()

# Create an agent
agent = Agent(name="my-agent", transport=transport)

# Define message handler
@agent.subscribe(channel=Channel("input-channel", transport=transport))
async def handle_message(message):
    # Process message
    result = await process(message)
    # Publish to output channel
    output_channel = Channel("output-channel", transport=transport)
    await output_channel.publish(result)

# Start the agent
await agent.start()
```

### Using Redis Streams (Recommended for Production)

Redis Streams provides durable message delivery with consumer groups, perfect for microservices and production deployments.

```python
from eggai import Agent, Channel, RedisTransport

# Create a Redis transport
transport = RedisTransport(url="redis://localhost:6379")

# Create an agent
agent = Agent(name="my-agent", transport=transport)

# Define message handler
@agent.subscribe(channel=Channel("input-channel", transport=transport))
async def handle_message(message):
    # Process message
    result = await process(message)
    # Publish to output channel
    output_channel = Channel("output-channel", transport=transport)
    await output_channel.publish(result)

# Start the agent
await agent.start()
```

### Using Kafka (Production - High Throughput)

Kafka is ideal for high-throughput, large-scale distributed streaming workloads.

```python
from eggai import Agent, Channel, KafkaTransport

# Create a Kafka transport
transport = KafkaTransport(
    bootstrap_servers="localhost:9092"
)

# Create an agent
agent = Agent(name="my-agent", transport=transport)

# Define message handler
@agent.subscribe(channel=Channel("input-topic", transport=transport))
async def handle_message(message):
    # Process message
    result = await process(message)
    # Publish to output topic
    output_channel = Channel("output-topic", transport=transport)
    await output_channel.publish(result)

# Start the agent
await agent.start()
```

## Transport Comparison

| Feature | In-Memory | Redis Streams | Kafka |
|---------|-----------|---------------|-------|
| **Use Case** | Testing, prototyping | Production microservices | Large-scale production |
| **Persistence** | ❌ No | ✅ Yes (AOF/RDB) | ✅ Yes (highly durable) |
| **Setup Complexity** | None | Simple | Moderate |
| **Throughput** | Very High | High (100K+ msgs/sec) | Very High (1M+ msgs/sec) |
| **Consumer Groups** | ❌ No | ✅ Native support | ✅ Native support |
| **Message Retention** | N/A | Time or count-based | Time or size-based |
| **Production Ready** | ❌ No | ✅ **Recommended** | ✅ **Recommended** |
| **Best For** | Unit tests, local dev | Most production workloads | High-throughput distributed systems |
| **Operational Cost** | None | Lower | Higher |

## Production Recommendations

For production deployments, we recommend:

- **Redis Streams**: Best for most production workloads. Simpler to operate, lower cost, excellent performance for microservices and event-driven architectures.
- **Kafka**: Best for very high-throughput requirements (1M+ messages/sec), complex stream processing, or when you need advanced features like exactly-once semantics.

The **In-Memory transport** should only be used for testing and development.

## Configuration

### Environment Variables

EggAI supports the following environment variables for configuration:

#### `EGGAI_NAMESPACE`
- **Purpose:** Prefix for all channel names to enable namespace isolation in shared transports
- **Default:** `"eggai"`
- **Usage:** Set to a custom namespace to isolate your application's channels
- **Example:**
  ```bash
  export EGGAI_NAMESPACE="myapp"
  # or
  EGGAI_NAMESPACE="prod" python my_agent.py
  ```
- **Effect:** If you set `EGGAI_NAMESPACE="prod"` and create a channel named `"events"`, the actual channel name used in the transport will be `"prod.events"`
- **Use Case:** Allows multiple applications or environments (dev, staging, prod) to share the same Kafka/Redis cluster without channel name collisions

## Interoperability

EggAI is designed as a meta-framework that enables seamless integration with other agent systems and protocols:

### Agent-to-Agent (A2A) Protocol

Connect EggAI agents with other agent frameworks and systems using the A2A protocol:

```bash
pip install eggai[a2a]
```

A2A enables:
- Cross-framework agent communication
- Standardized message formats for multi-agent systems
- Integration with existing agent ecosystems (AutoGen, LangChain, etc.)
- HTTP-based service discovery via AgentCards

**[Read full A2A documentation →](docs/A2A.md)**

### Model Context Protocol (MCP)

Integrate with LLM tools and services through MCP:

```bash
pip install eggai[mcp]
```

MCP support enables:
- LLM tool calling and function execution
- Context sharing across agent conversations
- Integration with Claude, GPT, and other LLM providers
- Standardized tool interfaces via FastMCP

**[Read full MCP documentation →](docs/MCP.md)**

### Transport Flexibility

EggAI's transport abstraction allows agents to communicate regardless of underlying infrastructure:
- **Hybrid deployments**: Mix local (in-memory) and distributed (Redis/Kafka) agents
- **Migration paths**: Start with Redis, scale to Kafka without changing agent code
- **Multi-cloud**: Deploy agents across different cloud providers using different transports
- **Custom transports**: Extend with your own transport implementations

### Extensibility

Build custom integrations through:
- **Custom Transport API**: Implement your own message broker backends
- **Middleware system**: Add cross-cutting concerns (logging, metrics, auth)
- **Message adapters**: Transform messages between different protocols
- **Plugin architecture**: Extend agent capabilities with reusable components

## Documentation

### Core Documentation

- **[Message Protocol](docs/MessageProtocol.md)**: CloudEvents-based message structure for agent communication
- **[A2A Integration](docs/A2A.md)**: Agent-to-Agent protocol for cross-framework interoperability
- **[MCP Integration](docs/MCP.md)**: Model Context Protocol for LLM tool integration

### Additional Resources

For full documentation, visit: https://eggai-tech.github.io/EggAI/

## License

MIT License - see LICENSE file for details
