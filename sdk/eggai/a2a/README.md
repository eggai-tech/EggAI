# EggAI A2A Protocol Implementation

This module provides [Agent2Agent (A2A) Protocol](https://a2a-protocol.org/) compliant communication for EggAI agents, enabling standardized interoperability between different AI agent systems.

## API Design

### Exposing an EggAI Agent to A2A

The primary API for exposing an EggAI agent via the A2A protocol is through the `agent.to_a2a()` method:

```python
from eggai import Agent
from eggai.transport import eggai_set_default_transport, KafkaTransport

# Configure transport
eggai_set_default_transport(lambda: KafkaTransport())

# Create your EggAI agent
agent = Agent("MyAwesomeAgent")

@agent.subscribe()
async def handle_messages(message):
    print(f"Received: {message}")
    # Your agent logic here

# Expose agent via A2A protocol
server = await agent.to_a2a(
    host="0.0.0.0",  # Default: "0.0.0.0" 
    port=8080        # Default: 8080
)

# Agent is now available at:
# - Agent Card: http://localhost:8080/.well-known/agent.json
# - JSON-RPC Endpoint: http://localhost:8080/
# - Health Check: http://localhost:8080/health
```

### API Methods

| Method | Description | Parameters |
|--------|-------------|------------|
| `agent.to_a2a(host, port)` | Expose agent via A2A protocol | `host` (str), `port` (int) |
| `server.stop()` | Stop the A2A server | None |

## A2A Protocol Endpoints

Once exposed, your agent provides these standard A2A endpoints:

### Agent Discovery
```bash
GET /.well-known/agent.json
```
Returns the Agent Card with capabilities and metadata.

### JSON-RPC Communication
```bash
POST /
Content-Type: application/json

{
  "jsonrpc": "2.0",
  "method": "message/send",
  "params": {
    "messages": [{
      "role": "user",
      "parts": [{
        "type": "text", 
        "content": "Hello from A2A!"
      }]
    }]
  },
  "id": "1"
}
```

### Health Check
```bash
GET /health
```
Returns agent health status.

## Client Usage

### Connecting to A2A Agents

```python
from eggai.a2a import A2AClient, MessageRole

# Connect to any A2A compliant agent
async with A2AClient("http://localhost:8080") as client:
    # Discover agent capabilities
    agent_card = await client.discover_agent()
    print(f"Connected to: {agent_card.name}")
    print(f"Capabilities: {agent_card.capabilities}")
    
    # Send a message
    task = await client.send_message(
        content="Hello, can you help me?",
        role=MessageRole.USER
    )
    
    # Check task status and get response
    completed_task = await client.get_task(task.id)
    for message in completed_task.messages:
        if message.role == MessageRole.ASSISTANT:
            for part in message.parts:
                print(f"Agent response: {part.content}")
```

### Client Methods

| Method | Description | Returns |
|--------|-------------|---------|
| `discover_agent()` | Get agent capabilities | `AgentCard` |
| `send_message(content, role, task_id)` | Send message to agent | `Task` |
| `get_task(task_id)` | Get task status and results | `Task` |
| `cancel_task(task_id)` | Cancel a running task | `Task` |
| `health_check()` | Check agent health | `bool` |

## Protocol Compliance

This implementation is fully compliant with A2A Protocol v0.2.6:

### Core Features
- **JSON-RPC 2.0** over HTTP(S) transport
- **Agent Discovery** via well-known URI standard
- **Task Management** with stateful operations
- **Message Handling** with roles, parts, and metadata
- **Error Handling** with standard JSON-RPC error codes

### Supported Methods
- `message/send` - Send messages to the agent
- `tasks/get` - Retrieve task status and results  
- `tasks/cancel` - Cancel running tasks

### Message Structure
- **Roles**: `user`, `assistant`, `system`
- **Part Types**: `text`, `file`, `data`
- **Task States**: `pending`, `running`, `completed`, `failed`, `cancelled`

## Implementation Details

### Architecture

```
┌─────────────────┐    HTTP/JSON-RPC 2.0    ┌─────────────────┐
│   A2A Client    │ ────────────────────────▶│   A2A Server    │
│                 │                          │                 │
│ - Agent Discovery│                          │ - Agent Card    │
│ - Message Sending│                          │ - Task Manager  │
│ - Task Management│                          │ - EggAI Bridge  │
└─────────────────┘                          └─────────────────┘
                                                       │
                                                       ▼
                                             ┌─────────────────┐
                                             │   EggAI Agent   │
                                             │                 │
                                             │ - Subscriptions │
                                             │ - Message Bus   │
                                             │ - Transport     │
                                             └─────────────────┘
```

### Key Components

#### 1. A2AServer (`server.py`)
- **FastAPI-based** HTTP server
- **JSON-RPC 2.0** request/response handling
- **Task state management** with persistent storage
- **EggAI integration** via message publishing
- **Agent Card generation** for discovery

#### 2. A2AClient (`client.py`)  
- **HTTP client** with async support
- **JSON-RPC 2.0** request formatting
- **Agent discovery** via well-known URI
- **Task tracking** and status polling
- **Error handling** with A2A-compliant exceptions

#### 3. Protocol Types (`types.py`)
- **Pydantic models** for type safety
- **A2A specification** compliant structures
- **JSON-RPC 2.0** request/response types
- **Agent Card** metadata schema

### Message Flow

1. **Client Request** → JSON-RPC 2.0 over HTTP
2. **Server Processing** → Parse request, validate params
3. **EggAI Integration** → Convert to EggAI message format
4. **Agent Processing** → Route through EggAI subscriptions  
5. **Response Generation** → Create A2A compliant response
6. **Task Management** → Store state, return to client

### Error Handling

The implementation follows JSON-RPC 2.0 error codes:

| Code | Error | Description |
|------|-------|-------------|
| -32700 | Parse error | Invalid JSON |
| -32601 | Method not found | Unknown A2A method |
| -32602 | Invalid params | Bad method parameters |
| -32603 | Internal error | Server processing error |

## Requirements

### Required Dependencies
```bash
pip install fastapi uvicorn httpx
```

### Optional Dependencies
The A2A module gracefully handles missing dependencies:

```python
# Without FastAPI - raises helpful error
agent = Agent("Test")
try:
    await agent.to_a2a()
except ImportError as e:
    print("Install: pip install fastapi uvicorn httpx")
```

## Testing

### Unit Tests
```bash
pytest tests/test_a2a_protocol.py -v
```

### Integration Testing
```bash
# Start an A2A agent
python examples/a2a_protocol_demo.py

# Test with curl
curl http://localhost:8080/.well-known/agent.json
curl -X POST http://localhost:8080/ \
  -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","method":"message/send","params":{"messages":[{"role":"user","parts":[{"type":"text","content":"Hello!"}]}]},"id":"1"}'
```

## Related Links

- [A2A Protocol Specification](https://a2a-protocol.org/)
- [A2A Protocol GitHub](https://github.com/a2a-protocol/a2a-protocol)
- [JSON-RPC 2.0 Specification](https://www.jsonrpc.org/specification)
- [EggAI Documentation](../../../README.md)

## Examples

See the `examples/` directory for complete working examples:

- [`a2a_protocol_demo.py`](../../examples/a2a_protocol_demo.py) - Full A2A protocol demonstration
- [`a2a_demo.py`](../../examples/a2a_demo.py) - Legacy example (deprecated)

## Contributing

When contributing to the A2A implementation:

1. **Follow A2A Specification** - Ensure compliance with the official protocol
2. **Test Compatibility** - Verify interoperability with other A2A implementations  
3. **Maintain Type Safety** - Use Pydantic models for all A2A structures
4. **Handle Errors Gracefully** - Follow JSON-RPC 2.0 error conventions
5. **Document Changes** - Update this README and protocol compliance notes