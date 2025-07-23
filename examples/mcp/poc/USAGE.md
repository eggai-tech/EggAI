# External Tools Adapter Usage Guide

## Quick Start

1. **Start Kafka (required for eggai messaging):**
   ```bash
   cd ../  # Go to main mcp example directory
   make docker-up
   ```

2. **Run the demo:**
   ```bash
   cd poc/
   python run_demo.py
   ```

## How It Works

### 1. Adapter Processes
Each adapter runs as a separate process:
```bash
# Start MCP filesystem adapter
python -c "from mcp_adapter import create_filesystem_adapter; from adapter_base import run_adapter; run_adapter(create_filesystem_adapter())"

# Start API adapter  
python -c "from api_adapter import MockAPIAdapter; from adapter_base import run_adapter; run_adapter(MockAPIAdapter())"
```

### 2. Agent Integration
Agents discover and use tools:
```python
from agent_integration import setup_external_tools

# Discover tools from adapters
tool_manager = await setup_external_tools("MyAgent", ["FileSystem", "MockAPI"])

# Use tools
result = await tool_manager.call_tool("MockAPI", "add", {"a": 5, "b": 3})
print(result)  # 8
```

### 3. DSPy Integration
Convert to DSPy tools:
```python
import dspy
from agent_integration import external_tools_to_dspy_tools

# Convert external tools to DSPy format
tools = external_tools_to_dspy_tools(tool_manager.get_all_tools(), tool_manager)

# Use in ReAct
react = dspy.ReAct(YourSignature, tools=tools)
```

## Architecture Benefits

### 🔄 **Standardized Protocol**
- All adapters implement same interface
- Consistent tool discovery and execution
- Easy to add new external systems

### 🏗️ **Modular Design**  
- Each adapter is an isolated process
- Failures don't affect other adapters
- Scale adapters independently

### ⚡ **Kafka-Based Communication**
- Reliable message delivery
- Async/non-blocking execution  
- Built-in load balancing

### 🔌 **Multi-Backend Support**
- MCP servers (stdio protocol)
- REST APIs (HTTP)
- Custom protocols (extend BaseAdapter)

### 🤖 **Agent Integration**
- Dynamic tool discovery at runtime
- Automatic tool injection into ReAct
- Error handling and timeouts

## Production Deployment

### Process Management
Use process manager like systemd or Docker:
```yaml
# docker-compose.yml
services:
  filesystem-adapter:
    build: .
    command: python -m poc.mcp_adapter
    environment:
      - KAFKA_BOOTSTRAP_SERVERS=kafka:9092
    
  api-adapter:
    build: .
    command: python -m poc.api_adapter  
    environment:
      - KAFKA_BOOTSTRAP_SERVERS=kafka:9092
```

### Monitoring
- Adapter health checks
- Tool execution metrics
- Error rate tracking

### Security
- Tool parameter validation
- Rate limiting per adapter
- Secure credential management

## Extending the System

### Add New Adapter Type
```python
class CustomAdapter(BaseAdapter):
    async def initialize_backend(self):
        # Connect to your system
        pass
        
    async def discover_tools(self):
        # Return ToolSchema list
        pass
        
    async def execute_tool(self, tool_name, parameters):
        # Execute and return ToolResult
        pass
```

### Add New Tool Discovery
```python
# Dynamic tool registration
await tool_manager.register_adapter("NewAdapter")
new_tools = await tool_manager.discover_tools(["NewAdapter"])
```

### Custom Agent Logic
```python
class SmartAgent:
    async def choose_tools(self, user_request):
        # LLM-based tool selection
        selected_tools = llm.choose_tools(user_request, available_tools)
        return selected_tools
```