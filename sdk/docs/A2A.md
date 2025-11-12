# Agent-to-Agent (A2A) Protocol Integration

EggAI supports the Agent-to-Agent (A2A) protocol, enabling seamless interoperability between different agent frameworks and systems.

## What is A2A?

The Agent-to-Agent (A2A) protocol is a standardized communication protocol that allows agents built with different frameworks to discover and interact with each other. It provides:

- **Cross-framework communication**: Connect EggAI agents with agents built using other frameworks
- **Service discovery**: Agents can discover each other's capabilities through AgentCards
- **Standardized interfaces**: Common message formats and API patterns
- **HTTP-based communication**: RESTful API with JSON-RPC support

## Installation

Install EggAI with A2A support:

```bash
pip install eggai[a2a]
```

This installs the required dependencies:
- `a2a-sdk`: Core A2A protocol implementation
- `uvicorn`: ASGI server for running A2A HTTP endpoints
- `starlette`: Web framework for A2A server

## Quick Start

Here's a complete example of creating an A2A-enabled agent:

```python
import asyncio
from eggai import Agent, Channel
from eggai.adapters.a2a import A2AConfig
from pydantic import BaseModel

# Define input/output data models
class AnalysisRequest(BaseModel):
    text: str
    language: str = "en"

class AnalysisResult(BaseModel):
    sentiment: str
    confidence: float
    keywords: list[str]

# Configure A2A
a2a_config = A2AConfig(
    agent_name="sentiment-analyzer",
    description="Analyzes text sentiment and extracts keywords",
    version="1.0.0",
    base_url="http://localhost:8080"
)

# Create agent with A2A config
agent = Agent(
    name="sentiment-agent",
    a2a_config=a2a_config
)

# Register handler as A2A skill
@agent.subscribe(
    channel=Channel("analysis-requests"),
    a2a_capability="analyze_sentiment",  # A2A skill name
    data_type=AnalysisRequest  # Input schema
)
async def analyze_sentiment(message: AnalysisRequest) -> AnalysisResult:
    """Analyze text sentiment and extract keywords."""
    # Your analysis logic here
    result = AnalysisResult(
        sentiment="positive",
        confidence=0.95,
        keywords=["example", "keyword"]
    )
    return result

async def main():
    # Start the agent
    await agent.start()

    # Start A2A HTTP server (makes skills discoverable)
    await agent.to_a2a(host="0.0.0.0", port=8080)

if __name__ == "__main__":
    asyncio.run(main())
```

## Configuration

### A2AConfig

Configure your A2A agent with the following parameters:

```python
from eggai.adapters.a2a import A2AConfig

config = A2AConfig(
    agent_name="my-agent",              # Required: Agent identifier
    description="What my agent does",   # Required: Agent description
    version="1.0.0",                    # Agent version (default: "1.0.0")
    base_url="http://localhost:8080",   # Base URL (default: "http://localhost:8080")
    security_schemes=None               # Optional: Security schemes
)
```

## Registering A2A Skills

To expose a message handler as an A2A skill, use the `a2a_capability` parameter:

```python
@agent.subscribe(
    channel=Channel("my-channel"),
    a2a_capability="skill_name",  # Exposes this as A2A skill
    data_type=InputModel          # Required: Input schema
)
async def my_handler(message: InputModel) -> OutputModel:
    """Skill description appears in AgentCard."""
    # Handler logic
    return OutputModel(...)
```

**Key points:**
- `a2a_capability`: The skill name that other agents will use to invoke this capability
- `data_type`: Pydantic model defining the input schema (required)
- Return type annotation: Pydantic model defining the output schema (optional but recommended)
- Docstring: Appears as the skill description in the AgentCard

## AgentCard

When you start the A2A server, EggAI automatically generates an AgentCard:

```python
await agent.to_a2a(host="0.0.0.0", port=8080)
```

The AgentCard includes:
- Agent metadata (name, description, version, URL)
- List of available skills with their schemas
- Input/output modes supported
- Security schemes

Other agents can discover your agent by fetching the AgentCard from:
```
GET http://localhost:8080/.well-known/agent.json
```

## Architecture

### How A2A Works with EggAI

```
┌─────────────────────────────────────────────────────────────┐
│  External Agent (any framework)                             │
│  - Discovers skills via AgentCard                           │
│  - Invokes skills via HTTP/JSON-RPC                         │
└────────────────────┬────────────────────────────────────────┘
                     │ HTTP Request
                     ▼
┌─────────────────────────────────────────────────────────────┐
│  A2A Server (Starlette/Uvicorn)                             │
│  - Receives skill invocation                                │
│  - Validates input against schema                           │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│  EggAIAgentExecutor                                         │
│  - Routes to registered handler                             │
│  - Executes handler function                                │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│  EggAI Agent Handler                                        │
│  - @agent.subscribe decorated function                      │
│  - Business logic execution                                 │
└────────────────────┬────────────────────────────────────────┘
                     │ Result
                     ▼
┌─────────────────────────────────────────────────────────────┐
│  Response sent back to external agent                       │
└─────────────────────────────────────────────────────────────┘
```

## Advanced Usage

### Multiple Skills

Register multiple skills on the same agent:

```python
@agent.subscribe(
    channel=Channel("analysis"),
    a2a_capability="sentiment_analysis",
    data_type=TextInput
)
async def analyze_sentiment(message: TextInput) -> SentimentOutput:
    """Analyze text sentiment."""
    return SentimentOutput(...)

@agent.subscribe(
    channel=Channel("extraction"),
    a2a_capability="entity_extraction",
    data_type=TextInput
)
async def extract_entities(message: TextInput) -> EntityOutput:
    """Extract named entities from text."""
    return EntityOutput(...)

@agent.subscribe(
    channel=Channel("summary"),
    a2a_capability="text_summarization",
    data_type=TextInput
)
async def summarize_text(message: TextInput) -> SummaryOutput:
    """Generate text summary."""
    return SummaryOutput(...)
```

All skills will be exposed through the same A2A server endpoint.

### Hybrid Architecture

Combine A2A (external HTTP) with EggAI messaging (internal):

```python
# External A2A skill that publishes to internal channels
@agent.subscribe(
    channel=Channel("external-requests"),
    a2a_capability="process_request",
    data_type=RequestInput
)
async def handle_external_request(message: RequestInput):
    """Receive requests from external agents via A2A."""
    # Publish to internal processing pipeline
    await Channel("internal-processing").publish(message)
    return {"status": "accepted"}

# Internal handler (not exposed via A2A)
@agent.subscribe(channel=Channel("internal-processing"))
async def process_internally(message):
    """Internal processing - not exposed to external agents."""
    # Complex internal logic
    await Channel("results").publish(processed_data)
```

### CORS Configuration

The A2A server includes CORS middleware by default. To customize:

```python
# CORS is automatically configured with:
# - allow_origins=["*"]
# - allow_credentials=True
# - allow_methods=["*"]
# - allow_headers=["*"]

# For production, you may want to fork and customize the middleware
```

## Integration Examples

### Connecting to AutoGen Agents

```python
# Your EggAI agent exposes A2A skills
# AutoGen agents can discover and call them

from autogen import Agent as AutoGenAgent

# AutoGen agent discovers your EggAI agent
autogen_agent = AutoGenAgent(
    name="autogen-coordinator",
    a2a_agents=["http://localhost:8080"]  # Your EggAI agent
)

# AutoGen can now invoke your EggAI agent's skills
```

### Connecting to LangChain Agents

```python
# EggAI agent with A2A
# LangChain can use it as a tool

from langchain.tools import Tool

eggai_tool = Tool(
    name="sentiment_analysis",
    description="Analyze text sentiment",
    func=lambda text: requests.post(
        "http://localhost:8080/skills/sentiment_analysis",
        json={"text": text}
    ).json()
)
```

## Best Practices

1. **Schema Definition**: Always use Pydantic models for input/output schemas
2. **Documentation**: Write clear docstrings - they appear in AgentCards
3. **Error Handling**: Handle errors gracefully within handlers
4. **Versioning**: Update the version field when changing skill interfaces
5. **Security**: Consider authentication/authorization for production deployments
6. **Monitoring**: Log A2A requests for observability
7. **Testing**: Test skills both via channels and via A2A HTTP endpoint

## Reference

### A2APlugin Methods

- `register_skill(skill_name, handler, data_type)`: Register a handler as an A2A skill
- `create_agent_card()`: Generate AgentCard from registered skills
- `start_server(host, port)`: Start A2A HTTP server

### Channel Patterns

A2A skills can use any EggAI transport (In-Memory, Redis, Kafka) for internal communication while exposing HTTP endpoints externally.

## Learn More

- [A2A Protocol Specification](https://github.com/a2a-protocol/spec)
- [A2A SDK Documentation](https://github.com/a2a-protocol/python-sdk)
- [EggAI Core Documentation](../README.md)
