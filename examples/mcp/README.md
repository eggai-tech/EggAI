# MCP Integration with EggAI

> **Connect your agents to external tools seamlessly**

This example demonstrates how to integrate Model Context Protocol (MCP) servers with EggAI agents, enabling them to access external tools like web APIs and file systems. Learn how to build a two-agent system where one handles user interaction and another processes requests with intelligent tool usage.

![MCP Integration Demo](https://raw.githubusercontent.com/eggai-tech/EggAI/refs/heads/main/docs/docs/assets/example-mcp.png)

## Agent Architecture

This example implements a **two-agent system** that demonstrates MCP integration patterns:

**Interface Agent** (`chat_agent/`): Simple console-based user interface  
- Captures user input from terminal  
- Displays responses and tool usage notifications  
- Routes messages to the processing agent via EggAI transport  

**Processing Agent** (`mcp_agent/`): Intelligent MCP-enabled agent  
- Uses DSPy ReAct for structured reasoning  
- Connects directly to MCP servers (fetch, filesystem)  
- Decides which tools to use based on user requests  
- Streams back responses and tool execution updates  

## Quick Start

```bash
# Setup everything
make setup
make docker-up

# Start chatting
make start
```

Then try: *"Fetch content from https://example.com and save it to a file"*

## Message Flow

```
User Input → Interface Agent → Processing Agent → MCP Tools → Response
            ↓ (EggAI)        ↓ (EggAI)       ↓ (stdio)
        Kafka Queue      Kafka Queue    MCP Servers
```

1. **Interface Agent** receives user input and forwards via EggAI messaging
2. **Processing Agent** gets the request and uses DSPy ReAct to reason about tool usage
3. **MCP Integration** connects to external servers (fetch, filesystem) as needed
4. **Tool Notifications** stream back through the agent chain to keep user informed
5. **Final Response** delivered to user with complete context of actions taken

## MCP Integration Features

This implementation shows how to:
- **Connect MCP Servers**: Direct stdio connections to fetch and filesystem servers
- **Tool Discovery**: Automatic registration of available MCP tools
- **Intelligent Selection**: DSPy ReAct reasoning to choose appropriate tools
- **Streaming Updates**: Real-time notifications of tool execution progress
- **Error Handling**: Graceful fallbacks when tools fail or are unavailable
- **Multi-step Workflows**: Chain multiple tool calls to complete complex tasks

## Project Structure

```
├── agents/
│   ├── chat_agent/     # Console interface
│   └── mcp_agent/      # The thinking agent
├── sandbox/            # Safe file playground
└── main.py            # Start here
```

## Architecture

This example implements a **two-agent system** with clear separation of concerns:

### Interface Agent (`chat_agent/`)
- Lightweight console interface using EggAI's base agent class
- Handles user input/output with minimal processing
- Forwards all reasoning tasks to the MCP agent via EggAI messaging

### MCP Agent (`mcp_agent/`)
- Uses DSPy's ReAct pattern for structured reasoning:
  1. **Think**: Understand what the user wants
  2. **Plan**: Decide which tools to use
  3. **Act**: Execute tools with reasoning
  4. **Reflect**: Learn from results
- Direct MCP server connections via stdio
- Tool wrapper classes that adapt MCP tools to DSPy format
- Streaming response generation with tool execution updates

### MCP Servers
- **Fetch Server**: Web content retrieval
- **Filesystem Server**: File operations in sandbox
- Connected via stdio for reliable communication

### Key Components

**MCP Integration** (`mcp_manager.py`):
- Manages connections to multiple MCP servers
- Automatic tool discovery and registration
- Error handling and server lifecycle management

**Agent Communication**:
- EggAI's Kafka-based messaging for reliable inter-agent communication
- Async message processing for responsive user experience
- Streaming updates during tool execution

## Key Integration Patterns

1. **Agent Separation**: Keep interface and processing logic in separate agents
2. **Tool Wrapping**: Adapt MCP tools to work with your reasoning framework
3. **Streaming Updates**: Provide real-time feedback during tool execution
4. **Error Resilience**: Handle MCP server failures gracefully
5. **Async Design**: Use EggAI's async capabilities for responsive tool usage

## Next Steps

- Add your own MCP servers to extend tool capabilities
- Implement custom tool selection logic in the processing agent
- Scale the MCP agent horizontally for high-throughput scenarios
- Explore multi-agent workflows with specialized MCP integrations
