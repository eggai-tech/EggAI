# EggAI Message Protocol

EggAI uses a standardized message protocol based on the **CloudEvents 1.0 specification** for all agent-to-agent communication. This ensures interoperability, traceability, and type-safe message handling across distributed agent systems.

## What is the Message Protocol?

The EggAI Message Protocol defines a standardized envelope for all messages exchanged between agents, regardless of the underlying transport (In-Memory, Redis, Kafka). It provides:

- **Standardized metadata**: Every message includes contextual information (source, type, timestamp)
- **Type safety**: Generic typing with Pydantic for compile-time type checking
- **Traceability**: Unique message IDs for correlation and debugging
- **CloudEvents compliance**: Follows CloudEvents 1.0 spec for broad ecosystem compatibility
- **Extensibility**: Support for custom data payloads via generics

## Core Message Structure

### BaseMessage[TData]

The `BaseMessage` is a generic Pydantic model that wraps all agent messages:

```python
from eggai.schemas import BaseMessage
from pydantic import BaseModel

class MyData(BaseModel):
    text: str
    count: int

# Create a strongly-typed message
class MyMessage(BaseMessage[MyData]):
    type: Literal["my.message.type"] = "my.message.type"

message = MyMessage(
    source="agent-1",
    type="my.message.type",
    data=MyData(text="Hello", count=42)
)
```

### Message Fields

All messages include the following CloudEvents-compliant fields:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `specversion` | `str` | Yes | CloudEvents version (always "1.0") |
| `id` | `UUID4` | Yes | Unique event identifier (auto-generated) |
| `source` | `str` | Yes | Identifies the event producer (e.g., "agent-1") |
| `type` | `str` | Yes | Event type (e.g., "user.created", "order.shipped") |
| `subject` | `Optional[str]` | No | Subject of the event in context |
| `time` | `Optional[datetime]` | No | Timestamp (auto-generated as ISO 8601) |
| `datacontenttype` | `Optional[str]` | No | Media type (default: "application/json") |
| `dataschema` | `Optional[str]` | No | URI of schema for data field |
| `data` | `TData` | Yes | Application-specific event payload |

## Quick Start

### Simple Message (Dict Data)

For quick prototyping, use the concrete `Message` class with dict data:

```python
from eggai.schemas import Message
from eggai import Agent, Channel

agent = Agent(name="simple-agent")

@agent.subscribe(channel=Channel("notifications"))
async def handle_notification(message: Message):
    print(f"From: {message.source}")
    print(f"Type: {message.type}")
    print(f"Data: {message.data}")
    print(f"ID: {message.id}")
    print(f"Time: {message.time}")

# Publish a message
await Channel("notifications").publish(
    Message(
        source="dashboard",
        type="alert.created",
        data={
            "severity": "high",
            "message": "CPU usage at 95%"
        }
    )
)
```

### Strongly-Typed Message

For production code, define custom Pydantic models:

```python
from eggai.schemas import BaseMessage
from pydantic import BaseModel
from typing import Literal

# Define your data schema
class AlertData(BaseModel):
    severity: Literal["low", "medium", "high", "critical"]
    message: str
    resource: str
    threshold: float

# Create a typed message
class AlertMessage(BaseMessage[AlertData]):
    type: Literal["alert.created"] = "alert.created"

# Use in agent
@agent.subscribe(channel=Channel("alerts"))
async def handle_alert(message: AlertMessage):
    # Type-safe access to data
    if message.data.severity == "critical":
        await escalate_alert(message.data)

    print(f"Alert from {message.source}: {message.data.message}")

# Publish with type safety
await Channel("alerts").publish(
    AlertMessage(
        source="monitoring-agent",
        data=AlertData(
            severity="critical",
            message="Database connection pool exhausted",
            resource="db-primary",
            threshold=0.95
        )
    )
)
```

## Message Type Patterns

### Event Notification

Use dot-separated naming for event types:

```python
class UserCreatedMessage(BaseMessage[UserData]):
    type: Literal["user.created"] = "user.created"

class OrderShippedMessage(BaseMessage[OrderData]):
    type: Literal["order.shipped"] = "order.shipped"

class PaymentFailedMessage(BaseMessage[PaymentData]):
    type: Literal["payment.failed"] = "payment.failed"
```

### Request-Response Pattern

Use `.request` and `.response` suffixes:

```python
class AnalysisRequest(BaseModel):
    text: str
    language: str = "en"

class AnalysisResult(BaseModel):
    sentiment: str
    confidence: float

class AnalysisRequestMessage(BaseMessage[AnalysisRequest]):
    type: Literal["analysis.request"] = "analysis.request"

class AnalysisResponseMessage(BaseMessage[AnalysisResult]):
    type: Literal["analysis.response"] = "analysis.response"

# Request handler
@agent.subscribe(channel=Channel("analysis-requests"))
async def handle_request(message: AnalysisRequestMessage):
    result = await analyze(message.data.text)

    await Channel("analysis-responses").publish(
        AnalysisResponseMessage(
            source="analyzer-agent",
            data=result
        )
    )
```

### Command Pattern

Use imperative verbs for commands:

```python
class ProcessOrderCommand(BaseMessage[OrderData]):
    type: Literal["order.process"] = "order.process"

class CancelSubscriptionCommand(BaseMessage[SubscriptionData]):
    type: Literal["subscription.cancel"] = "subscription.cancel"

class UpdateInventoryCommand(BaseMessage[InventoryData]):
    type: Literal["inventory.update"] = "inventory.update"
```

## Advanced Usage

### Message Correlation

Use the `id` field to correlate request/response:

```python
from uuid import uuid4

# Send request
request_id = uuid4()
await Channel("requests").publish(
    RequestMessage(
        id=request_id,  # Explicit ID
        source="client-agent",
        data=RequestData(...)
    )
)

# In response handler, include original request ID
@agent.subscribe(channel=Channel("requests"))
async def handle_request(message: RequestMessage):
    await Channel("responses").publish(
        ResponseMessage(
            source="server-agent",
            subject=str(message.id),  # Reference original request
            data=ResponseData(...)
        )
    )
```

### Message Subject

Use `subject` to add context:

```python
await Channel("user-events").publish(
    UserMessage(
        source="auth-service",
        type="user.updated",
        subject="user-12345",  # User ID as subject
        data=UserData(...)
    )
)

await Channel("order-events").publish(
    OrderMessage(
        source="order-service",
        type="order.status_changed",
        subject="order-67890",  # Order ID as subject
        data=OrderData(...)
    )
)
```

### Custom Timestamps

Override the default timestamp:

```python
import datetime

await Channel("events").publish(
    EventMessage(
        source="batch-processor",
        time=datetime.datetime(2025, 1, 1, 0, 0, 0, tzinfo=datetime.UTC),
        data=EventData(...)
    )
)
```

### Schema References

Reference external schemas:

```python
await Channel("events").publish(
    EventMessage(
        source="api-gateway",
        dataschema="https://example.com/schemas/user-event-v1.json",
        data=UserData(...)
    )
)
```

## Message Validation

### Automatic Validation

Pydantic automatically validates messages:

```python
class StrictData(BaseModel):
    score: float  # Must be float
    count: int    # Must be int

class StrictMessage(BaseMessage[StrictData]):
    type: Literal["strict.message"] = "strict.message"

# This will raise ValidationError
try:
    message = StrictMessage(
        source="test",
        data=StrictData(score="invalid", count=10)  # Wrong type!
    )
except ValidationError as e:
    print(e.errors())
```

### Custom Validators

Add custom validation logic:

```python
from pydantic import field_validator

class ScoreData(BaseModel):
    score: float

    @field_validator('score')
    def validate_score(cls, v):
        if not 0 <= v <= 1:
            raise ValueError('Score must be between 0 and 1')
        return v

class ScoreMessage(BaseMessage[ScoreData]):
    type: Literal["score.updated"] = "score.updated"
```

## Serialization

### JSON Serialization

Messages serialize to CloudEvents-compliant JSON:

```python
message = AlertMessage(
    source="monitoring",
    data=AlertData(
        severity="high",
        message="Alert",
        resource="server-1",
        threshold=0.9
    )
)

# Serialize to JSON
json_str = message.model_dump_json()
print(json_str)
# {
#   "specversion": "1.0",
#   "id": "550e8400-e29b-41d4-a716-446655440000",
#   "source": "monitoring",
#   "type": "alert.created",
#   "time": "2025-11-12T20:30:00Z",
#   "datacontenttype": "application/json",
#   "data": {
#     "severity": "high",
#     "message": "Alert",
#     "resource": "server-1",
#     "threshold": 0.9
#   }
# }

# Deserialize from JSON
restored = AlertMessage.model_validate_json(json_str)
```

### Dict Representation

```python
# To dict
message_dict = message.model_dump()

# From dict
restored = AlertMessage.model_validate(message_dict)
```

## Transport Integration

The Message Protocol works seamlessly with all EggAI transports:

### In-Memory Transport

```python
from eggai.transport.memory import InMemoryTransport

transport = InMemoryTransport()
channel = Channel("events", transport=transport)

await channel.publish(
    EventMessage(source="local", data=EventData(...))
)
```

### Redis Streams

```python
from eggai.transport.redis import RedisTransport

transport = RedisTransport(url="redis://localhost:6379")
channel = Channel("events", transport=transport)

await channel.publish(
    EventMessage(source="redis-agent", data=EventData(...))
)
```

### Kafka

```python
from eggai.transport.kafka import KafkaTransport

transport = KafkaTransport(bootstrap_servers="localhost:9092")
channel = Channel("events", transport=transport)

await channel.publish(
    EventMessage(source="kafka-agent", data=EventData(...))
)
```

All transports automatically serialize/deserialize messages using the protocol.

## Best Practices

### 1. Always Use Typed Messages in Production

```python
# ❌ Avoid in production
Message(source="x", type="event", data={"foo": "bar"})

# ✅ Use typed messages
class MyMessage(BaseMessage[MyData]):
    type: Literal["my.event"] = "my.event"
```

### 2. Use Descriptive Source Names

```python
# ❌ Generic names
source="agent1"

# ✅ Descriptive names
source="billing-service"
source="notification-agent"
source="ml-classifier-v2"
```

### 3. Follow Type Naming Conventions

```python
# Events (past tense)
type="user.created"
type="order.shipped"

# Commands (imperative)
type="order.process"
type="user.notify"

# Queries/Requests
type="user.query"
type="analytics.request"
```

### 4. Include Relevant Context in Subject

```python
# Good: Entity ID as subject
subject="user-12345"
subject="order-67890"

# Good: Correlation ID
subject="request-abc123"
```

### 5. Keep Data Payloads Focused

```python
# ❌ Too much data
class BloatedData(BaseModel):
    user: UserModel
    orders: list[OrderModel]
    preferences: PreferencesModel
    history: HistoryModel

# ✅ Focused payload
class OrderCreatedData(BaseModel):
    order_id: str
    user_id: str
    total: float
```

### 6. Version Your Message Types

```python
class UserMessageV1(BaseMessage[UserDataV1]):
    type: Literal["user.created.v1"] = "user.created.v1"

class UserMessageV2(BaseMessage[UserDataV2]):
    type: Literal["user.created.v2"] = "user.created.v2"
```

## CloudEvents Compliance

EggAI's Message Protocol is fully compliant with CloudEvents 1.0:

- ✅ All required CloudEvents fields are present
- ✅ Field names match CloudEvents specification
- ✅ ISO 8601 timestamp format
- ✅ UUID v4 for message IDs
- ✅ JSON serialization format

This means EggAI messages can be consumed by any CloudEvents-compatible system.

## Reference

### Imports

```python
from eggai.schemas import BaseMessage, Message
from pydantic import BaseModel
from typing import Literal, Optional
from uuid import UUID
import datetime
```

### Common Patterns

```python
# Event notification
class EventMessage(BaseMessage[EventData]):
    type: Literal["domain.event"] = "domain.event"

# Request
class RequestMessage(BaseMessage[RequestData]):
    type: Literal["service.request"] = "service.request"

# Response
class ResponseMessage(BaseMessage[ResponseData]):
    type: Literal["service.response"] = "service.response"

# Command
class CommandMessage(BaseMessage[CommandData]):
    type: Literal["resource.action"] = "resource.action"

# Error
class ErrorMessage(BaseMessage[ErrorData]):
    type: Literal["system.error"] = "system.error"
```

## Learn More

- [CloudEvents Specification](https://cloudevents.io/)
- [Pydantic Documentation](https://docs.pydantic.dev/)
- [EggAI Documentation](../index.md)
- [Transport Documentation](transport.md)
