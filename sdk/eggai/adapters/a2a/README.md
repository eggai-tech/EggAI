# EggAI A2A Integration

This package provides Agent-to-Agent (A2A) protocol support for EggAI agents with minimal code changes.

## Features

- **Simple Integration**: Add A2A support with just a few parameter changes
- **Dual Protocol Support**: Same handlers work for both EggAI channels and A2A HTTP requests
- **Auto-Discovery**: Automatically generate A2A skills from handler decorators
- **Type Safety**: Input/output schemas from Pydantic models
- **Direct Execution**: A2A requests call handlers directly (no Kafka routing)
- **Standards Compliant**: Uses official A2A SDK patterns

## Installation

```bash
# Basic EggAI (already installed)
pip install eggai

# A2A dependencies (required for A2A functionality)
pip install a2a-sdk uvicorn
```

## Quick Start

### 1. Regular EggAI Agent

```python
from eggai import Agent, Channel
from pydantic import BaseModel

class OrderRequest(BaseModel):
    customer_id: str
    total: float

agent = Agent("OrderAgent")

@agent.subscribe(channel=Channel("orders"), data_type=OrderRequest)
async def process_order(message):
    # Regular EggAI handler
    return {"order_id": "ORD-123", "status": "confirmed"}
```

### 2. A2A-Enabled Agent

```python
from eggai import Agent, Channel, A2AConfig
from eggai.schemas import BaseMessage
from pydantic import BaseModel

class OrderRequest(BaseModel):
    customer_id: str
    total: float

class OrderResponse(BaseModel):
    order_id: str
    status: str

# Define BaseMessage types
class OrderMessage(BaseMessage[OrderRequest]):
    type: str = "order.request"

# Step 1: Add A2A configuration
a2a_config = A2AConfig(
    agent_name="OrderAgent",
    description="Processes customer orders"
)

# Step 2: Pass config to Agent
agent = Agent("OrderAgent", a2a_config=a2a_config)

# Step 3: Add a2a_capability parameter
@agent.subscribe(
    channel=Channel("orders"),
    data_type=OrderMessage,
    a2a_capability="process_order"
)
async def process_order(message: OrderMessage) -> OrderResponse:
    """Process a customer order with validation."""
    # Access data from message.data
    return OrderResponse(order_id="ORD-123", status="confirmed")

# Step 4: Start A2A server
await agent.start()
await agent.to_a2a(host="0.0.0.0", port=8080)
```

## Architecture

```
┌─────────────────┐    ┌─────────────────┐
│   A2A Client    │    │  EggAI Client   │
│   (HTTP/JSON)   │    │  (Pub/Sub)      │
└─────────┬───────┘    └─────────┬───────┘
          │                      │
          ▼                      ▼
┌─────────────────────────────────────────┐
│           EggAI Agent                   │
│  ┌─────────────────────────────────┐    │
│  │    EggAIAgentExecutor           │    │
│  │  (A2A → Direct Handler Calls)   │    │
│  └─────────────────────────────────┘    │
│  ┌─────────────────────────────────┐    │
│  │     Handler Functions           │    │
│  │   (Same Business Logic)         │    │
│  └─────────────────────────────────┘    │
│  ┌─────────────────────────────────┐    │
│  │     EggAI Transport Layer       │    │
│  │   (Kafka, InMemory, etc.)       │    │
│  └─────────────────────────────────┘    │
└─────────────────────────────────────────┘
```

## Key Components

### A2AConfig

Simple configuration for A2A functionality:

```python
from eggai import A2AConfig

config = A2AConfig(
    agent_name="MyAgent",
    description="What the agent does",
    version="1.0.0",
    base_url="http://localhost:8080"
)
```

### Enhanced Subscribe Decorator

Regular EggAI `@agent.subscribe()` with A2A support using BaseMessage classes:

```python
from eggai.schemas import BaseMessage

class MyInputType(BaseModel):
    field1: str

class MyMessage(BaseMessage[MyInputType]):
    type: str = "my_skill.request"

@agent.subscribe(
    channel=Channel("my_channel"),
    data_type=MyMessage,
    a2a_capability="my_skill"
)
async def my_handler(message: MyMessage) -> MyOutputType:
    """This docstring becomes the skill description."""
    data = message.data  # Access the MyInputType data
    return result
```

### EggAIAgentExecutor

Translates A2A requests to direct handler calls:

- Extracts skill name from A2A request
- Parses A2A message content to handler format
- Calls EggAI handler directly (no Kafka)
- Converts handler result to A2A response

## Message Flow

### EggAI Flow (Unchanged)
1. Message published to Channel
2. Transport delivers to handler
3. Handler processes and publishes result

### A2A Flow (New)
1. HTTP POST to A2A server endpoint
2. EggAIAgentExecutor extracts skill_id from request metadata
3. Handler called directly with EggAI message format
4. Result returned as A2A response

### Dual Protocol Handler

The same handler processes both protocols:

```python
@agent.subscribe(
    channel=Channel("orders"),
    data_type=OrderMessage, 
    a2a_capability="process_order"
)
async def process_order(message: OrderMessage) -> OrderResponse:
    # Business logic works for both protocols
    order_data = message.data  # OrderRequest object
    
    # Process the order
    result = OrderResponse(
        order_id=f"ORD-{order_data.customer_id}",
        status="confirmed"
    )
    
    # A2A: return directly (captured by executor)
    # EggAI: can also publish to channels if needed
    return result
```

## Testing

### View Agent Card

```bash
curl http://localhost:8080/.well-known/agent.json
```

### A2A Client Usage

Use the A2A SDK client to interact with the agent:

```python
from a2a.client import A2ACardResolver, A2AClient
from a2a.types import SendMessageRequest, MessageSendParams, Message, Part, DataPart, Role
import httpx

async with httpx.AsyncClient() as client:
    resolver = A2ACardResolver(httpx_client=client, base_url="http://localhost:8080")
    agent_card = await resolver.get_agent_card()
    
    a2a_client = A2AClient(httpx_client=client, agent_card=agent_card)
    
    message = Message(
        role=Role.user,
        parts=[Part(root=DataPart(data={"customer_id": "123", "total": 99.99}))],
        message_id="unique-id"
    )
    
    request = SendMessageRequest(
        id="request-id",
        params=MessageSendParams(
            message=message,
            metadata={"skill_id": "process_order"}
        )
    )
    
    response = await a2a_client.send_message(request)
```

## Demo

See the `demo/` directory for complete examples:

- `simple_demo.py` - Complete A2A-enabled agent with greeting and math skills
- `client.py` - A2A client that tests all agent capabilities

```bash
# Run the demo server
python -m eggai.adapters.a2a.demo.simple_demo

# In another terminal, run the client
python -m eggai.adapters.a2a.demo.client
```

This provides a working example of A2A integration with EggAI agents!