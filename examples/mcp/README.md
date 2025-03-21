# EggAI MCP Integration

This example demonstrates how to integrate [Model Context Protocol (MCP)](https://github.com/modelcontextprotocol/protocol) with EggAI, allowing you to easily connect and use MCP-compatible tools in your EggAI agents.

## Overview

<img src="https://raw.githubusercontent.com/eggai-tech/EggAI/refs/heads/main/docs/docs/assets/example-mcp.png" style="max-width: 600px;"/>

This example provides a way to integrate MCP tools with EggAI's agent framework, allowing agents to communicate with MCP-compatible tools through a standardized interface. The integration supports:

1. Running MCP tools as EggAI agents
2. Agent-to-agent communication using EggAI channels
3. Tool discovery and usage in LLM conversations

## Components

- `agents/`: Directory containing agent implementations
  - `chat_agent/`: Chat agent that can use MCP tools
    - `agent.py`: Main chat application implementation
  - `fetch_mcp/`: Fetch MCP adapter implementation
    - `mcp_adapter.py`: Adapter for fetch operations
  - `filesystem_mcp/`: Filesystem MCP adapter implementation
    - `mcp_adapter.py`: Adapter for filesystem operations
- `utils/`: Utility functions for MCP integration
  - `eggai_mcp_adapter.py`: Base MCP adapter functionality
  - `eggai_mcp_adapter_client.py`: Client for MCP adapters
- `sandbox/`: Directory used by the filesystem MCP server

## Architecture

The example follows a layered architecture:

1. **MCP Adapters**: Adapters that integrate MCP-compatible tools with EggAI's channel system
   - `fetch_mcp/mcp_adapter.py`: Adapter for HTTP fetch operations
   - `filesystem_mcp/mcp_adapter.py`: Adapter for filesystem operations
2. **EggAI Utilities**: Helper classes and functions for MCP integration
   - `utils/eggai_mcp_adapter.py`: Base adapter functionality
   - `utils/eggai_mcp_adapter_client.py`: Client for interacting with MCP adapters
3. **Chat Agent**: A client agent that can discover and use MCP tools through EggAI channels
   - `chat_agent/agent.py`: Main chat application implementation

## Prerequisites

- Python 3.9+
- Kafka (provided via Docker Compose)
- Node.js and npm (for filesystem MCP server)
- uvx (for fetch MCP server)

Ensure you have a valid OpenAI API key set in your environment:

```bash
export OPENAI_API_KEY="your-api-key"
```

## Setup

1. Clone the repository and navigate to the MCP example directory:
   ```
   cd examples/mcp
   ```

2. Set up the environment using the provided Makefile:
   ```
   make setup
   ```

3. Start the Kafka infrastructure with Docker Compose:
   ```
   make docker-up
   ```

## Running the Example

You can run the services individually or all at once:

### Start individual services

1. Start the Fetch MCP adapter:
   ```
   make start-mcp-fetch
   ```

2. Start the Filesystem MCP adapter:
   ```
   make start-mcp-filesystem
   ```

3. Start the chat agent:
   ```
   make start-mcp-chat
   ```

### Start all services at once

```
make start-all
```

The chat agent leverages message streaming capabilities and provides enhanced tool mode processing for better interaction with the MCP adapters.

## Interacting with the Example

Once all services are running, you can interact with the chat interface. The agent has access to tools from both MCP services and can:

- Fetch data from the web using the Fetch MCP server
- Read and write files using the Filesystem MCP server

Example interactions:
- "Can you fetch the content from https://example.com and save it to a file?"
- "What files are available in the sandbox directory?"
- "Read the content of file-1.txt"

## Cleanup

When you're done with the example, you can clean up:

1. Stop the Docker services:
   ```
   make docker-down
   ```

2. Clean up the environment:
   ```
   make clean
   ```

## Next Steps

Ready to explore further? Check out:

- **Advanced Examples:** Discover more complex use cases in the [examples](https://github.com/eggai-tech/EggAI/tree/main/examples/) folder.
- **Contribution Guidelines:** Get involved and help improve EggAI!
- **GitHub Issues:** [Submit a bug or feature request](https://github.com/eggai-tech/eggai/issues).
- **Documentation:** Refer to the official docs for deeper insights.