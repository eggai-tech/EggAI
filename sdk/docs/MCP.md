# Model Context Protocol (MCP) Integration

EggAI supports the Model Context Protocol (MCP), enabling agents to integrate with LLM tools and services for enhanced AI capabilities.

## What is MCP?

The Model Context Protocol (MCP) is a standardized protocol for connecting LLMs with external tools, data sources, and services. It provides:

- **Tool calling**: LLMs can discover and invoke external tools
- **Context sharing**: Share structured context across agent conversations
- **Standardized interfaces**: Common patterns for LLM tool integration
- **Multi-provider support**: Works with Claude, GPT, and other LLM providers

## Installation

Install EggAI with MCP support:

```bash
pip install eggai[mcp]
```

This installs the required dependencies:
- `fastmcp`: Fast MCP server implementation
- Related MCP protocol libraries

## Quick Start

Here's a complete example of creating an MCP adapter agent:

```python
import asyncio
from eggai.adapters.mcp import run_mcp_adapter
from fastmcp import FastMCP

# Create FastMCP server with tools
mcp = FastMCP("my-tools")

@mcp.tool()
def calculate_sum(a: float, b: float) -> float:
    """Add two numbers together."""
    return a + b

@mcp.tool()
def get_weather(city: str) -> dict:
    """Get current weather for a city."""
    # Your weather API logic here
    return {
        "city": city,
        "temperature": 72,
        "conditions": "sunny"
    }

@mcp.tool()
async def search_database(query: str) -> list[dict]:
    """Search the database for records."""
    # Your database search logic here
    return [{"id": 1, "title": "Example"}]

# Run MCP adapter
if __name__ == "__main__":
    asyncio.run(run_mcp_adapter(
        name="my-tools-adapter",
        mcp_server=mcp
    ))
```

## How It Works

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  LLM Application (Claude, GPT, etc.)                        │
│  - Needs external tool capabilities                         │
│  - Sends tool list/call requests via channels               │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│  EggAI Channels                                             │
│  - tools.{adapter}.list.in  (tool list requests)            │
│  - tools.{adapter}.calls.in (tool call requests)            │
│  - tools.{adapter}.list.out (tool list responses)           │
│  - tools.{adapter}.calls.out (tool call responses)          │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│  MCP Adapter Agent (EggAI)                                  │
│  - Subscribes to request channels                           │
│  - Translates between EggAI and MCP                         │
│  - Publishes responses                                      │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│  FastMCP Server                                             │
│  - list_tools() - Returns available tools                   │
│  - call_tool(name, params) - Executes tool                  │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│  Your Tool Functions                                        │
│  - Decorated with @mcp.tool()                               │
│  - Business logic implementation                            │
└─────────────────────────────────────────────────────────────┘
```

### Channel Pattern

The MCP adapter uses a standardized channel naming convention:

```
tools.{adapter_name}.list.in     → Tool list requests
tools.{adapter_name}.list.out    → Tool list responses
tools.{adapter_name}.calls.in    → Tool call requests
tools.{adapter_name}.calls.out   → Tool call responses
```

## Message Types

### Tool List Request

Request to discover available tools:

```python
from eggai.adapters.mcp.models import ToolListRequestMessage, ToolListRequest
from uuid import uuid4

request = ToolListRequestMessage(
    source="llm-agent",
    data=ToolListRequest(
        call_id=uuid4(),
        adapter_name="my-tools-adapter"
    )
)

await Channel("tools.my-tools-adapter.list.in").publish(request)
```

### Tool List Response

Response with available tools:

```python
from eggai.adapters.mcp.models import ToolListResponseMessage, ToolListResponse, ExternalTool

response = ToolListResponseMessage(
    source="my-tools-adapter",
    data=ToolListResponse(
        call_id=original_call_id,
        tools=[
            ExternalTool(
                name="calculate_sum",
                description="Add two numbers together",
                parameters={
                    "type": "object",
                    "properties": {
                        "a": {"type": "number"},
                        "b": {"type": "number"}
                    }
                },
                return_type={"type": "number"}
            )
        ]
    )
)
```

### Tool Call Request

Request to execute a tool:

```python
from eggai.adapters.mcp.models import ToolCallRequestMessage, ToolCallRequest

request = ToolCallRequestMessage(
    source="llm-agent",
    data=ToolCallRequest(
        call_id=uuid4(),
        tool_name="calculate_sum",
        parameters={"a": 5, "b": 3}
    )
)

await Channel("tools.my-tools-adapter.calls.in").publish(request)
```

### Tool Call Response

Response with tool execution result:

```python
from eggai.adapters.mcp.models import ToolCallResponseMessage, ToolCallResponse

# Success response
response = ToolCallResponseMessage(
    source="my-tools-adapter",
    data=ToolCallResponse(
        call_id=original_call_id,
        tool_name="calculate_sum",
        data=8,
        is_error=False
    )
)

# Error response
error_response = ToolCallResponseMessage(
    source="my-tools-adapter",
    data=ToolCallResponse(
        call_id=original_call_id,
        tool_name="calculate_sum",
        data="Division by zero error",
        is_error=True
    )
)
```

## Complete Example: LLM Agent with MCP Tools

Here's a complete example showing an LLM agent using MCP tools:

```python
import asyncio
from uuid import uuid4
from eggai import Agent, Channel
from eggai.adapters.mcp import run_mcp_adapter
from eggai.adapters.mcp.models import (
    ToolListRequestMessage,
    ToolListRequest,
    ToolCallRequestMessage,
    ToolCallRequest,
)
from fastmcp import FastMCP

# 1. Define MCP tools
mcp = FastMCP("calculator")

@mcp.tool()
def add(a: float, b: float) -> float:
    """Add two numbers."""
    return a + b

@mcp.tool()
def multiply(a: float, b: float) -> float:
    """Multiply two numbers."""
    return a * b

# 2. Start MCP adapter in background
async def start_mcp_adapter():
    await run_mcp_adapter(name="calculator", mcp_server=mcp)

# 3. Create LLM agent that uses MCP tools
async def llm_agent():
    agent = Agent(name="llm-agent")
    adapter_name = "calculator"

    # Subscribe to tool responses
    @agent.subscribe(
        channel=Channel(f"tools.{adapter_name}.list.out"),
        auto_offset_reset="latest"
    )
    async def handle_tool_list(message):
        print(f"Available tools: {[t.name for t in message.data.tools]}")

    @agent.subscribe(
        channel=Channel(f"tools.{adapter_name}.calls.out"),
        auto_offset_reset="latest"
    )
    async def handle_tool_result(message):
        if message.data.is_error:
            print(f"Tool error: {message.data.data}")
        else:
            print(f"Tool result: {message.data.data}")

    await agent.start()

    # Discover tools
    list_request = ToolListRequestMessage(
        source="llm-agent",
        data=ToolListRequest(
            call_id=uuid4(),
            adapter_name=adapter_name
        )
    )
    await Channel(f"tools.{adapter_name}.list.in").publish(list_request)

    await asyncio.sleep(1)  # Wait for response

    # Call a tool
    call_request = ToolCallRequestMessage(
        source="llm-agent",
        data=ToolCallRequest(
            call_id=uuid4(),
            tool_name="add",
            parameters={"a": 10, "b": 5}
        )
    )
    await Channel(f"tools.{adapter_name}.calls.in").publish(call_request)

    await asyncio.sleep(1)  # Wait for result

# 4. Run both
async def main():
    await asyncio.gather(
        start_mcp_adapter(),
        llm_agent()
    )

if __name__ == "__main__":
    asyncio.run(main())
```

## Advanced Usage

### Multiple MCP Adapters

Run multiple MCP adapters for different tool categories:

```python
# Database tools
db_mcp = FastMCP("database")

@db_mcp.tool()
def query_users(filter: str) -> list[dict]:
    """Query users from database."""
    return []

# API tools
api_mcp = FastMCP("external-apis")

@api_mcp.tool()
def call_weather_api(location: str) -> dict:
    """Call external weather API."""
    return {}

# Run both adapters
await asyncio.gather(
    run_mcp_adapter(name="database", mcp_server=db_mcp),
    run_mcp_adapter(name="external-apis", mcp_server=api_mcp)
)
```

### Async Tools

MCP supports async tools for I/O operations:

```python
@mcp.tool()
async def fetch_data(url: str) -> dict:
    """Fetch data from remote URL."""
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            return await response.json()

@mcp.tool()
async def query_database(query: str) -> list[dict]:
    """Query database asynchronously."""
    async with database.connect() as conn:
        result = await conn.execute(query)
        return await result.fetchall()
```

### Tool with Complex Types

Use Pydantic models for complex parameters:

```python
from pydantic import BaseModel

class SearchParams(BaseModel):
    query: str
    limit: int = 10
    filters: dict = {}

class SearchResult(BaseModel):
    id: str
    title: str
    score: float

@mcp.tool()
def search(params: SearchParams) -> list[SearchResult]:
    """Search with complex parameters."""
    # Your search logic
    return [
        SearchResult(id="1", title="Result 1", score=0.95)
    ]
```

## Integration Patterns

### With Redis Transport

```python
from eggai.transport import eggai_set_default_transport
from eggai.transport.redis import RedisTransport

# Use Redis for MCP communication
eggai_set_default_transport(lambda: RedisTransport(url="redis://localhost:6379"))

# Now all MCP channels use Redis
await run_mcp_adapter(name="tools", mcp_server=mcp)
```

### With Kafka Transport

```python
from eggai.transport import eggai_set_default_transport
from eggai.transport.kafka import KafkaTransport

# Use Kafka for high-throughput tool calling
eggai_set_default_transport(lambda: KafkaTransport(bootstrap_servers="localhost:9092"))

await run_mcp_adapter(name="tools", mcp_server=mcp)
```

## Best Practices

1. **Tool Naming**: Use clear, descriptive names for tools
2. **Documentation**: Write detailed docstrings - they're sent to LLMs
3. **Type Hints**: Always use type hints for parameters and return values
4. **Error Handling**: Handle errors gracefully and return meaningful error messages
5. **Async When Needed**: Use async tools for I/O operations
6. **Tool Granularity**: Keep tools focused on single responsibilities
7. **Testing**: Test tools independently before integrating with MCP

## Reference

### MCP Message Models

- `ToolListRequestMessage`: Request available tools
- `ToolListResponseMessage`: Response with tool list
- `ToolCallRequestMessage`: Execute a tool
- `ToolCallResponseMessage`: Tool execution result
- `ExternalTool`: Tool metadata (name, description, schemas)

### Channel Convention

```python
def tool_channels(adapter_name: str):
    return {
        "list_in": f"tools.{adapter_name}.list.in",
        "list_out": f"tools.{adapter_name}.list.out",
        "calls_in": f"tools.{adapter_name}.calls.in",
        "calls_out": f"tools.{adapter_name}.calls.out",
    }
```

## Learn More

- [MCP Specification](https://modelcontextprotocol.io/)
- [FastMCP Documentation](https://github.com/jlowin/fastmcp)
- [EggAI Core Documentation](../README.md)
- [Building LLM Agents with MCP](https://anthropic.com/mcp)
