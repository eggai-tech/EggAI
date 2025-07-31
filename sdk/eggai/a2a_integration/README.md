# EggAI A2A Integration (a2a_integration)

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
from pydantic import BaseModel

class OrderRequest(BaseModel):
    customer_id: str
    total: float

class OrderResponse(BaseModel):
    order_id: str
    status: str

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
    data_type=OrderRequest,
    a2a_capability="process_order"  # Only new parameter!
)
async def process_order(message) -> OrderResponse:
    """Process a customer order with validation."""  # Becomes skill description
    # Same business logic as before
    return OrderResponse(order_id="ORD-123", status="confirmed")

# Step 4: Start A2A server
await agent.start()  # Regular EggAI startup
await agent.to_a2a(host="0.0.0.0", port=8080)  # Start A2A server
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

Regular EggAI `@agent.subscribe()` with optional A2A support:

```python
@agent.subscribe(
    channel=Channel("my_channel"),     # Regular EggAI
    data_type=MyInputType,             # For input schema
    a2a_capability="my_skill"          # A2A skill name
)
async def my_handler(message) -> MyOutputType:  # Return type for output schema
    """This docstring becomes the skill description."""
    # Business logic here
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
1. HTTP POST to `/a2a/tasks`
2. EggAIAgentExecutor extracts skill name
3. Handler called directly with EggAI message format
4. Result returned as A2A response

### Dual Protocol Handler

The same handler processes both protocols:

```python
@agent.subscribe(
    channel=Channel("orders"),
    data_type=OrderRequest, 
    a2a_capability="process_order"
)
async def process_order(message) -> OrderResponse:
    # Business logic works for both protocols
    result = await business_logic(message.data)
    
    # EggAI: publish to channel (optional)
    await Channel("results").publish(result_message)
    
    # A2A: return directly (captured by executor)
    return result
```

## Testing

### View Agent Card

```bash
curl http://localhost:8080/.well-known/agent-card.json
```

### Make A2A Request

```bash
curl -X POST http://localhost:8080/a2a/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "skill": "process_order",
    "message": {
      "role": "user",
      "content": [{"type": "data", "data": {"customer_id": "123", "total": 99.99}}]
    }
  }'
```

## Demo

See the `demo/` directory for complete examples:

- `simple_agent.py` - Before/after comparison
- `running_a2a_agent.py` - Live A2A server with multiple skills
- `test_basic.py` - Basic functionality tests

```bash
# Run demos
python -m eggai.a2a.demo.simple_agent
python -m eggai.a2a.demo.running_a2a_agent
python -m eggai.a2a.demo.test_basic
```

## Benefits

1. **Minimal Changes**: Add A2A with 4 simple modifications
2. **Dual Protocol**: Same business logic for EggAI and A2A
3. **Auto-Discovery**: Skills generated from decorators
4. **Type Safety**: Schemas from Pydantic models
5. **Direct Execution**: Fast A2A responses via direct calls
6. **Standards Compliant**: Official A2A SDK integration

This approach provides the simplest possible path to add A2A capabilities to existing EggAI agents!