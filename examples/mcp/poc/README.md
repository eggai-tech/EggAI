# External Tools Integration PoC

This PoC demonstrates a standardized architecture for connecting eggai agents to external tools through adapter processes using Kafka messaging.

## Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌────────────────────┐
│  Agent Process  │    │  Adapter Process │    │  External System   │
│                 │    │                  │    │                    │
│ ┌─────────────┐ │    │ ┌──────────────┐ │    │ ┌────────────────┐ │
│ │ DSPy ReAct  │ │◄──►│ │   Adapter    │ │◄──►│ │ MCP Server     │ │
│ │ Agent       │ │    │ │              │ │    │ │ REST API       │ │
│ │             │ │    │ │ - Discovery  │ │    │ │ Custom Service │ │
│ │ - Tool Calls│ │    │ │ - Execution  │ │    │ │                │ │
│ └─────────────┘ │    │ └──────────────┘ │    │ └────────────────┘ │
└─────────────────┘    └──────────────────┘    └────────────────────┘
         │                       │                        
    Kafka Channels          Standard Protocol         
    - tools.list.*        - Tool Discovery              
    - tools.call.*        - Tool Execution               
```

## Key Features

1. **Standardized Messaging**: All adapters use consistent Kafka channel protocol
2. **Dynamic Tool Discovery**: Agents discover tools at runtime from adapters
3. **Process Isolation**: Each adapter runs independently for reliability  
4. **Multiple Backends**: Support for MCP servers, REST APIs, custom protocols
5. **DSPy Integration**: Tools automatically available in ReAct reasoning
6. **Async/Sync Handling**: Proper async-to-sync conversion for DSPy compatibility

## Protocol

### Tool Discovery
- **Channel**: `tools.list.{adapter_name}`  
- **Request**: `{"action": "list_tools"}`
- **Response**: `{"adapter_name": "...", "tools": [...]}`

### Tool Execution  
- **Channel**: `tools.call.{adapter_name}`
- **Request**: `{"action": "call_tool", "name": "...", "parameters": {...}, "call_id": "..."}`
- **Response**: `{"result": {...}, "success": true/false, "error": "...", "call_id": "..."}`

## Core Components

### Infrastructure
- **`adapter_base.py`** - Base adapter class with standardized protocol
- **`mcp_adapter.py`** - MCP server adapter (stdio communication)
- **`api_adapter.py`** - REST API adapter (JSON configuration-based)
- **`agent_integration.py`** - Agent-side tool discovery and execution

### Demo Application  
- **`demo/react_agent.py`** - DSPy ReAct agent with external tools
- **`demo/console_interface.py`** - Interactive console interface
- **`demo/simple_tool_integration.py`** - DSPy tool conversion layer
- **`demo/react_signature.py`** - DSPy signature for external tools

### Entry Points
- **`demo/run_react_demo.py`** - Main demo orchestration
- **`demo/start_filesystem_adapter.py`** - FileSystem MCP adapter
- **`demo/start_react_agent.py`** - ReAct agent process
- **`demo/start_console.py`** - Console interface process

## Quick Start

1. **Prerequisites**:
   ```bash
   # Install dependencies
   pip install -r requirements.txt
   
   # Start Redpanda (Kafka)
   cd ../../../../demo && docker compose up -d
   ```

2. **Run Demo**:
   ```bash
   cd demo
   make demo
   ```

3. **Interact**:
   - Use natural language to request file operations
   - Example: "List the files in the directory"
   - Example: "Read the project notes file"

## Configuration

### Environment Variables
- `EGGAI_NAMESPACE=eggai` - Kafka topic prefix
- `OPENAI_API_KEY` - Required for DSPy ReAct agent

### MCP Adapter
The FileSystem adapter provides file operations within allowed directories:
- `demo/test_files/` - Sandboxed directory for file operations

### API Adapter Configuration
Create JSON config files defining tools:
```json
{
  "tools": [
    {
      "name": "tool_name",
      "description": "Tool description", 
      "endpoint": "/api/endpoint",
      "method": "POST",
      "parameters": {
        "type": "object",
        "properties": {
          "param": {"type": "string", "description": "Parameter description"}
        },
        "required": ["param"]
      },
      "output": {
        "type": "object", 
        "properties": {
          "result": {"type": "string", "description": "Result description"}
        }
      }
    }
  ]
}
```

## Architecture Benefits

1. **Scalability**: Each adapter runs independently
2. **Reliability**: Process isolation prevents cascading failures
3. **Flexibility**: Easy to add new tool backends
4. **Standardization**: Consistent protocol across all adapters
5. **Agent Agnostic**: Works with any agent framework

## Tool Types Supported

- **MCP Servers**: Model Context Protocol servers (stdio)
- **REST APIs**: HTTP/JSON services with static configuration  
- **Custom Protocols**: Implement BaseAdapter for any backend

## Development

### Adding New Adapters
1. Inherit from `BaseAdapter`
2. Implement required methods:
   - `initialize_backend()`
   - `discover_tools()`
   - `execute_tool()`
   - `cleanup_backend()`

### Testing
- Use `reset_redpanda.sh` to clean Kafka state
- Check logs in `demo/logs/` for debugging
- Monitor Kafka topics via Redpanda console