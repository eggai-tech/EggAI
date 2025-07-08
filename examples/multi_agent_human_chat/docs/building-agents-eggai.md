# Building Agents Guide

## Quick Start

Create an intelligent agent in 4 steps:

1. **Structure**
```
agents/your_agent/
├── main.py           # Entry point
├── agent.py          # Core logic
├── config.py         # Settings
├── types.py          # Messages
├── tools.py          # Capabilities
└── dspy_modules/     # AI components
```

2. **Configuration** (`config.py`)
```python
class AgentConfig(BaseModel):
    name: str = "your_agent"
    kafka_bootstrap_servers: str = Field(env="KAFKA_BOOTSTRAP_SERVERS")
    language_model: str = Field(env="YOUR_AGENT_LANGUAGE_MODEL")
    language_model_api_base: str = Field(env="YOUR_AGENT_LANGUAGE_MODEL_API_BASE")
```

3. **Messages** (`types.py`)
```python
class YourAgentInquiry(TracedMessage):
    type: str = "YourAgentInquiry"
    query: str
    
class YourAgentResponse(TracedMessage):
    type: str = "YourAgentResponse"
    response: str
```

4. **Agent Implementation** (`agent.py`)
```python
from eggai import Agent
from libraries.observability.tracing import TracedReAct, create_tracer

class YourAgent:
    def __init__(self, config):
        self.agent = Agent(name=config.name)
        self.tracer = create_tracer(config.name)
        self.react = TracedReAct(
            signature=YourSignature,
            tools=AVAILABLE_TOOLS,
            tracer=self.tracer
        )
        
    @agent.subscribe(channel="agents", type="YourAgentInquiry")
    async def handle_inquiry(self, message: YourAgentInquiry):
        response = await self.react(query=message.query)
        await self.agent.publish(
            channel="human_stream",
            message=YourAgentResponse(
                response=response.response,
                correlation_id=message.correlation_id
            )
        )
```

## Key Concepts

### EggAI SDK
- **Channels**: `human`, `agents`, `human_stream`, `audit_logs`
- **Pattern**: Subscribe to channels, filter by message type
- **Publishing**: Send responses back via `human_stream`

### DSPy Integration
```python
# Define signature
class YourSignature(dspy.Signature):
    """What your agent does."""
    query: str = dspy.InputField()
    response: str = dspy.OutputField()

# Create tools
def your_tool(param: str) -> str:
    """Tool description for ReAct."""
    return result
```

### Running Your Agent
```python
# main.py
from eggai import eggai_main

@eggai_main
async def main():
    config = load_config(AgentConfig)
    agent = YourAgent(config)
    await agent.start()
```

## Integration

1. **Add to docker-compose.yml**:
```yaml
your-agent:
  build: .
  dockerfile: agents/your_agent/Dockerfile
  environment:
    - KAFKA_BOOTSTRAP_SERVERS=redpanda:9092
    - YOUR_AGENT_LANGUAGE_MODEL=${YOUR_AGENT_LANGUAGE_MODEL}
```

2. **Configure Triage routing** (if needed)
3. **Test**: `make test-your-agent`

## Best Practices

- **Stateless**: No shared state between instances
- **Type-safe**: Use Pydantic for all messages
- **Observable**: Include tracing and logging
- **Testable**: Unit test tools and message handlers

---

**Previous:** [Multi-Agent Communication](multi-agent-communication.md) | **Next:** [ReAct Framework with DSPy](react-framework-dspy.md)