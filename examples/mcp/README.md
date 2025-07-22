# EggAI MCP Integration

> **Smart agents that think and act with tools**

Build intelligent agents that can reason step-by-step and use real tools through the Model Context Protocol (MCP). This example demonstrates how EggAI agents leverage DSPy's ReAct framework to interact with external systems.

![MCP Integration Demo](https://raw.githubusercontent.com/eggai-tech/EggAI/refs/heads/main/docs/docs/assets/example-mcp.png)

## Features

**Smart Reasoning**: Agents think before they act using DSPy's ReAct pattern  
**Real Tools**: Connect to web APIs and filesystems through MCP  
**Live Chat**: Stream responses as agents work  
**Multi-turn**: Maintain context across conversations  

## Quick Start

```bash
# Setup everything
make setup
make docker-up

# Start chatting
make start
```

Then try: *"Fetch content from https://example.com and save it to a file"*

## How It Works

```
User Input → Console Agent → MCP Agent → Tools → Response
```

- **Console Agent**: Your chat interface
- **MCP Agent**: The brain that reasons and acts
- **MCP Tools**: Web fetch, file operations, and more

## What You Can Do

Ask your agent to:
- Fetch web content and analyze it
- Create, read, and modify files
- Combine multiple tools to solve complex tasks
- Reason through problems step by step

## Project Structure

```
├── agents/
│   ├── chat_agent/     # Console interface
│   └── mcp_agent/      # The thinking agent
├── sandbox/            # Safe file playground
└── main.py            # Start here
```

## Requirements

- Python 3.9+
- Docker (for message queue)
- OpenAI API key

```bash
export OPENAI_API_KEY="your-key-here"
```

## Commands

| Command | Purpose |
|---------|---------|
| `make setup` | Install dependencies |
| `make docker-up` | Start infrastructure |
| `make start` | Run the example |
| `make clean` | Clean up everything |

## Architecture Deep Dive

### The Brain (MCP Agent)
Uses DSPy's ReAct pattern to:
1. **Think**: Understand what the user wants
2. **Plan**: Decide which tools to use
3. **Act**: Execute tools with reasoning
4. **Reflect**: Learn from results

### The Tools (MCP Servers)
- **Fetch Server**: Web content retrieval
- **Filesystem Server**: File operations in sandbox

### The Connection (EggAI Transport)
Kafka-based messaging for reliable agent communication

## Next Steps

- Explore more [examples](https://github.com/eggai-tech/EggAI/tree/main/examples/)
- Add your own MCP tools
- Build multi-agent workflows
- [Contribute](https://github.com/eggai-tech/eggai/issues) to EggAI

---

*Ready to build something amazing? Start exploring the code!*