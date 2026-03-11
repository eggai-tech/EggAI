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
from eggai import Agent, Channel
from eggai.transport.memory import InMemoryTransport

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
from eggai import Agent, Channel
from eggai.transport.redis import RedisTransport

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
from eggai import Agent, Channel
from eggai.transport.kafka import KafkaTransport

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

## Reliable Message Delivery (Redis Streams)

### Pending Entries List (PEL) and Retry Streams

With `NACK_ON_ERROR` (the default), a handler exception leaves the message in Redis's Pending
Entries List (PEL). FastStream only reads new messages, so a failed message would be stuck
forever without intervention.

Enable SDK-managed retry by setting `retry_on_idle_ms` on any subscription:

```python
from eggai import Agent, Channel
from eggai.transport import RedisTransport

transport = RedisTransport(url="redis://localhost:6379")
agent = Agent("order-service", transport=transport)
orders = Channel("orders", transport=transport)

@agent.subscribe(channel=orders, retry_on_idle_ms=30_000)
async def handle_order(message):
    # If this raises, the message stays in the PEL.
    # After 30s idle the reclaimer moves it to eggai.orders.retry
    # and this same handler is called again.
    await process_order(message)

await agent.start()
```

The SDK automatically:
1. Starts a background reclaimer that scans the PEL every 15 seconds (configurable via `retry_reclaim_interval_s`).
2. Moves idle messages (older than `retry_on_idle_ms`) to a dedicated `{channel}.retry` stream.
3. Subscribes the same handler to the retry stream.
4. Runs a second reclaimer on the retry stream that re-queues back to itself (no `.retry.retry` chain).

**Delivery guarantee:** at-least-once. `XADD` and `XACK` are not atomic — a crash between
them will re-deliver the message on the next cycle. Handlers must be **idempotent**.
Two fields are injected on retry delivery to aid deduplication:

| Field | Value |
|-------|-------|
| `_retry_count` | `"1"`, `"2"`, … — incremented on each reclaim cycle |
| `_original_message_id` | Redis stream ID of the original message |

**Constraints:**
- `min_idle_time` (FastStream XAUTOCLAIM) and `retry_on_idle_ms` are mutually exclusive on the same subscription — mixing them raises `ValueError`.
- Binary (non-UTF-8) field values are not supported; use JSON-serialisable payloads.

### Retry delivery reference

```
Main stream  (eggai.orders)
    │
    ├── FastStream consumer  (group/consumer: order-service-handle_order-1)
    │       on exception → NACK → message stays in main PEL
    │
    └── Reclaimer            (consumer: order-service-handle_order-1-reclaimer)
            every 15s: XPENDING → idle > 30s → XCLAIM → XADD orders.retry → XACK

Retry stream (eggai.orders.retry)
    │
    ├── FastStream consumer  (group: order-service-handle_order-1-retry)
    │       same handler — on exception → NACK → message stays in retry PEL
    │
    └── Reclaimer            (target: same retry stream — no .retry.retry chain)
            every 15s: XPENDING → idle > 30s → XCLAIM → XADD orders.retry → XACK
```

## Production Recommendations

For production deployments, we recommend:

- **Redis Streams**: Best for most production workloads. Simpler to operate, lower cost, excellent performance for microservices and event-driven architectures.
- **Kafka**: Best for very high-throughput requirements (1M+ messages/sec), complex stream processing, or when you need advanced features like exactly-once semantics.

The **In-Memory transport** should only be used for testing and development.

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

**[Read full A2A documentation →](https://docs.egg-ai.com/)**

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

**[Read full MCP documentation →](https://docs.egg-ai.com/)**

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

- **[Message Protocol](https://docs.egg-ai.com/sdk/message/)**: CloudEvents-based message structure for agent communication
- **[Agent](https://docs.egg-ai.com/sdk/agent/)**: Core agent abstraction for building autonomous units
- **[Channel](https://docs.egg-ai.com/sdk/channel/)**: Communication layer for event publishing and subscription

### Additional Resources

For full documentation, visit: https://docs.egg-ai.com/

## License

MIT License - see LICENSE file for details
