# Multi-Agent Communication

This document describes how agents communicate within the multi-agent insurance support system using event-driven architecture and the EggAI SDK.

## Overview

The multi-agent system uses an event-driven architecture where agents communicate asynchronously through channels. This design enables loose coupling, scalability, and resilience.

## Communication Infrastructure

### Kafka/Redpanda Message Bus

The system uses Redpanda (Kafka-compatible) as the central message bus for all agent communication:

- **Broker**: `localhost:19092` (configurable via `KAFKA_BOOTSTRAP_SERVERS`)
- **Protocol**: Event streaming with consumer groups
- **Message Format**: JSON with distributed tracing headers
- **Delivery Guarantees**: At-least-once delivery

### Communication Channels

The system defines four primary channels:

1. **`human`** - User messages from the frontend
   - Producers: Frontend Agent
   - Consumers: Triage Agent, Audit Agent

2. **`human_stream`** - Streaming responses to users
   - Producers: All specialized agents
   - Consumers: Frontend Agent, Audit Agent

3. **`agents`** - Inter-agent communication
   - Producers: Triage Agent, specialized agents
   - Consumers: All agents (filtered by message type)

4. **`audit_logs`** - Compliance and monitoring
   - Producers: Audit Agent
   - Consumers: External monitoring systems

## EggAI SDK Framework

### Channel-Based Communication

Agents use the EggAI SDK to subscribe to channels and handle messages:

```python
from eggai import Agent

agent = Agent(
    name="billing",
    transport_config={"bootstrap_servers": "localhost:19092"}
)

@agent.subscribe(channel="agents", type="BillingInquiry")
async def handle_billing_inquiry(message: BillingInquiry):
    # Process billing inquiry
    response = await process_billing(message)
    
    # Send response back
    await agent.publish(
        channel="human_stream",
        message=response,
        correlation_id=message.correlation_id
    )
```

### Message Types

Each agent defines strongly-typed messages using Pydantic:

```python
class BillingInquiry(BaseMessage):
    query: str
    policy_number: Optional[str]
    customer_id: str
```

### Message Filtering

Agents can filter messages by:
- **Type**: Only receive specific message types
- **Source**: Filter by sending agent
- **Headers**: Custom routing logic

## Message Flow Patterns

### 1. User Request Flow

```
User → Frontend Agent → [human] → Triage Agent
                                      ↓
                                 [agents] → Specialized Agent
                                              ↓
                                        [human_stream] → Frontend → User
```

### 2. Inter-Agent Collaboration

```
Claims Agent → [agents] → Policies Agent (get policy details)
                 ↓
         [agents] ← Response
```

### 3. Streaming Responses

Agents can stream partial results using the `human_stream` channel:

```python
async for chunk in generate_response():
    await agent.publish(
        channel="human_stream",
        message=StreamChunk(content=chunk),
        correlation_id=correlation_id
    )
```

## Distributed Tracing

All messages include distributed tracing headers:
- **Trace ID**: Unique identifier for the entire conversation
- **Span ID**: Identifier for individual operations
- **Parent Span**: Links related operations

This enables end-to-end observability through Grafana and Tempo.

## Error Handling

### Retry Logic

The SDK implements automatic retry for transient failures:
- Exponential backoff
- Maximum retry attempts: 3
- Dead letter queue for failed messages

### Circuit Breaker

Agents implement circuit breaker patterns:
- Open circuit after 5 consecutive failures
- Half-open state after 30 seconds
- Automatic recovery on success

## Best Practices

### 1. Message Design
- Keep messages small and focused
- Include correlation IDs for request tracking
- Use versioning for message schema evolution

### 2. Channel Usage
- Use `agents` channel for internal communication
- Reserve `human_stream` for user-facing responses
- Implement proper error messages for user communication

### 3. Performance
- Batch messages when possible
- Use streaming for large responses
- Implement proper backpressure handling

### 4. Security
- Validate all incoming messages
- Sanitize user input
- Use SSL/TLS for production deployments

## Configuration

Agent communication is configured through environment variables:

```bash
# Kafka Configuration
KAFKA_BOOTSTRAP_SERVERS=localhost:19092
KAFKA_SECURITY_PROTOCOL=SSL
KAFKA_SSL_CA_LOCATION=/path/to/ca-cert
KAFKA_SSL_CERT_LOCATION=/path/to/cert
KAFKA_SSL_KEY_LOCATION=/path/to/key

# Agent Configuration
AGENT_NAME=billing
AGENT_CONSUMER_GROUP=billing-agents
AGENT_MAX_CONCURRENT_MESSAGES=10
```

## Monitoring

Monitor agent communication through:
- **Redpanda Console**: Message flow visualization
- **Grafana Dashboards**: Throughput and latency metrics
- **Prometheus Metrics**: Consumer lag and error rates
- **Distributed Tracing**: End-to-end request tracking

---

**Previous:** [Agent Capabilities Overview](agents-overview.md) | **Next:** [Building Agents Guide](building-agents-eggai.md)