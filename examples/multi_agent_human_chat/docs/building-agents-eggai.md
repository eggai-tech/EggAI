# Building Agents with EggAI SDK

This guide explains how to create intelligent agents using the EggAI SDK combined with DSPy's ReAct pattern for the multi-agent insurance support system.

## Overview

Creating an agent involves:
1. Setting up the agent with EggAI SDK
2. Defining message types and channels
3. Implementing DSPy ReAct for intelligent reasoning
4. Adding tools and capabilities
5. Integrating with the multi-agent system

## Project Structure

A typical agent has this structure:

```
agents/your_agent/
├── __init__.py
├── main.py              # Entry point
├── agent.py             # Agent implementation
├── config.py            # Configuration
├── types.py             # Message type definitions
├── tools.py             # Tool implementations
├── dspy_modules/        # DSPy components
│   ├── __init__.py
│   ├── signatures.py    # DSPy signatures
│   └── react_agent.py   # ReAct implementation
└── tests/               # Unit tests
```

## Step 1: Define Configuration

Create `config.py` to define agent settings:

```python
from pydantic import BaseModel, Field
from typing import Optional

class AgentConfig(BaseModel):
    name: str = "your_agent"
    description: str = "Agent for handling specific tasks"
    
    # Kafka configuration
    kafka_bootstrap_servers: str = Field(
        default="localhost:19092",
        env="KAFKA_BOOTSTRAP_SERVERS"
    )
    
    # Language model configuration
    language_model: str = Field(
        default="lmstudio-community/gemma-3-12b-it-qat",
        env="YOUR_AGENT_LANGUAGE_MODEL"
    )
    language_model_api_base: str = Field(
        default="http://localhost:1234/v1",
        env="YOUR_AGENT_LANGUAGE_MODEL_API_BASE"
    )
    
    # Agent-specific settings
    max_concurrent_messages: int = 10
    response_timeout: int = 30
```

## Step 2: Define Message Types

Create `types.py` for strongly-typed messages:

```python
from typing import Optional, List
from pydantic import BaseModel
from libraries.models import TracedMessage

class YourAgentInquiry(TracedMessage):
    """Message type for incoming requests to your agent."""
    type: str = "YourAgentInquiry"
    query: str
    context: Optional[dict] = None
    
class YourAgentResponse(TracedMessage):
    """Response from your agent."""
    type: str = "YourAgentResponse"
    response: str
    metadata: Optional[dict] = None
```

## Step 3: Implement Tools

Create `tools.py` for agent capabilities:

```python
from typing import Dict, List
import json

def get_customer_data(customer_id: str) -> Dict:
    """
    Retrieve customer data from the database.
    
    Args:
        customer_id: The customer identifier
        
    Returns:
        Customer information dictionary
    """
    # Implementation - connect to database or API
    return {
        "customer_id": customer_id,
        "name": "John Doe",
        "status": "active"
    }

def update_record(record_id: str, data: Dict) -> bool:
    """
    Update a record in the system.
    
    Args:
        record_id: The record to update
        data: New data for the record
        
    Returns:
        Success status
    """
    # Implementation
    return True

# Export available tools
AVAILABLE_TOOLS = [
    get_customer_data,
    update_record
]
```

## Step 4: Create DSPy Components

### Define Signatures (`dspy_modules/signatures.py`):

```python
import dspy

class YourAgentSignature(dspy.Signature):
    """Process user requests intelligently."""
    
    query: str = dspy.InputField(
        desc="The user's request or question"
    )
    context: str = dspy.InputField(
        desc="Additional context about the conversation",
        default=""
    )
    response: str = dspy.OutputField(
        desc="Helpful response addressing the user's request"
    )
```

### Implement ReAct Agent (`dspy_modules/react_agent.py`):

```python
import dspy
from libraries.observability.tracing import TracedReAct, create_tracer
from ..tools import AVAILABLE_TOOLS
from .signatures import YourAgentSignature

class YourReActAgent:
    def __init__(self, config):
        # Initialize DSPy with language model
        dspy.configure(
            lm=dspy.LM(
                model=config.language_model,
                api_base=config.language_model_api_base,
                temperature=0.7
            )
        )
        
        # Create tracer for observability
        self.tracer = create_tracer(f"{config.name}_agent")
        
        # Initialize ReAct with tools
        self.react = TracedReAct(
            signature=YourAgentSignature,
            tools=AVAILABLE_TOOLS,
            name=f"{config.name}_react",
            tracer=self.tracer,
            max_iters=5
        )
        
        # Load optimized prompts if available
        self.load_optimized_prompts()
    
    def load_optimized_prompts(self):
        """Load optimized prompts from training."""
        try:
            self.react.load("optimized_prompts.json")
        except FileNotFoundError:
            pass  # Use default prompts
    
    async def process_request(self, query: str, context: dict = None) -> str:
        """Process a user request using ReAct reasoning."""
        context_str = json.dumps(context) if context else ""
        
        # Execute ReAct reasoning
        result = self.react(
            query=query,
            context=context_str
        )
        
        return result.response
```

## Step 5: Implement the Agent

Create `agent.py` with the main agent logic:

```python
from eggai import Agent
from libraries.models import TracedMessage
from libraries.observability.logging import logger
from .config import AgentConfig
from .types import YourAgentInquiry, YourAgentResponse
from .dspy_modules.react_agent import YourReActAgent

class YourAgent:
    def __init__(self, config: AgentConfig):
        self.config = config
        
        # Initialize EggAI agent
        self.agent = Agent(
            name=config.name,
            transport_config={
                "bootstrap_servers": config.kafka_bootstrap_servers
            }
        )
        
        # Initialize ReAct agent
        self.react_agent = YourReActAgent(config)
        
        # Subscribe to channels
        self._setup_subscriptions()
    
    def _setup_subscriptions(self):
        """Set up message subscriptions."""
        
        # Subscribe to agent channel for your message type
        @self.agent.subscribe(
            channel="agents",
            type="YourAgentInquiry"
        )
        async def handle_inquiry(message: YourAgentInquiry):
            """Handle incoming inquiries."""
            logger.info(f"Processing inquiry: {message.correlation_id}")
            
            try:
                # Process with ReAct
                response = await self.react_agent.process_request(
                    query=message.query,
                    context=message.context
                )
                
                # Send response
                await self.agent.publish(
                    channel="human_stream",
                    message=YourAgentResponse(
                        response=response,
                        correlation_id=message.correlation_id,
                        conversation_id=message.conversation_id
                    )
                )
                
            except Exception as e:
                logger.error(f"Error processing inquiry: {e}")
                await self._send_error_response(message, str(e))
    
    async def _send_error_response(self, original_message: TracedMessage, error: str):
        """Send error response to user."""
        await self.agent.publish(
            channel="human_stream",
            message=YourAgentResponse(
                response=f"I encountered an error: {error}",
                correlation_id=original_message.correlation_id,
                conversation_id=original_message.conversation_id
            )
        )
    
    async def start(self):
        """Start the agent."""
        logger.info(f"Starting {self.config.name} agent")
        await self.agent.start()
    
    async def stop(self):
        """Stop the agent."""
        logger.info(f"Stopping {self.config.name} agent")
        await self.agent.stop()
```

## Step 6: Create Entry Point

Create `main.py` to run the agent:

```python
import asyncio
from eggai import eggai_main
from libraries.config import load_config
from libraries.observability.logging import logger
from .agent import YourAgent
from .config import AgentConfig

@eggai_main
async def main():
    """Main entry point for the agent."""
    # Load configuration
    config = load_config(AgentConfig)
    
    # Create and start agent
    agent = YourAgent(config)
    
    try:
        await agent.start()
        logger.info(f"{config.name} agent started successfully")
        
        # Keep running until interrupted
        await asyncio.Event().wait()
        
    except KeyboardInterrupt:
        logger.info("Shutting down agent")
    finally:
        await agent.stop()

if __name__ == "__main__":
    asyncio.run(main())
```

## Step 7: Add to Docker Compose

Add your agent to `docker-compose.yml`:

```yaml
your-agent:
  build:
    context: .
    dockerfile: agents/your_agent/Dockerfile
  environment:
    - KAFKA_BOOTSTRAP_SERVERS=redpanda:9092
    - YOUR_AGENT_LANGUAGE_MODEL=${YOUR_AGENT_LANGUAGE_MODEL:-lmstudio-community/gemma-3-12b-it-qat}
    - YOUR_AGENT_LANGUAGE_MODEL_API_BASE=${YOUR_AGENT_LANGUAGE_MODEL_API_BASE:-http://host.docker.internal:1234/v1}
  depends_on:
    - redpanda
  networks:
    - app-network
```

## Advanced Features

### Streaming Responses

For long responses, use streaming:

```python
from libraries.models import StreamingChunk

async def handle_streaming_inquiry(message: YourAgentInquiry):
    """Handle inquiry with streaming response."""
    
    # Stream response chunks
    async for chunk in self.react_agent.stream_response(message.query):
        await self.agent.publish(
            channel="human_stream",
            message=StreamingChunk(
                content=chunk,
                correlation_id=message.correlation_id,
                is_final=False
            )
        )
    
    # Send completion marker
    await self.agent.publish(
        channel="human_stream",
        message=StreamingChunk(
            content="",
            correlation_id=message.correlation_id,
            is_final=True
        )
    )
```

### Inter-Agent Communication

Communicate with other agents:

```python
async def get_policy_details(policy_id: str) -> dict:
    """Get policy details from the Policies agent."""
    
    # Send request to Policies agent
    response = await self.agent.request(
        channel="agents",
        message=PoliciesInquiry(
            type="PoliciesInquiry",
            query=f"Get details for policy {policy_id}",
            correlation_id=str(uuid.uuid4())
        ),
        timeout=10
    )
    
    return response.data
```

### Custom Routing

Add routing logic for the Triage agent:

```python
# In types.py
class YourAgentClassification(BaseModel):
    """Classification for routing to your agent."""
    keywords: List[str] = ["your", "specific", "keywords"]
    confidence_threshold: float = 0.8
    
    @classmethod
    def should_route(cls, text: str, confidence: float) -> bool:
        """Determine if message should route to this agent."""
        text_lower = text.lower()
        has_keyword = any(kw in text_lower for kw in cls.keywords)
        return has_keyword and confidence >= cls.confidence_threshold
```

## Testing Your Agent

Create unit tests in `tests/test_agent.py`:

```python
import pytest
from unittest.mock import Mock, AsyncMock
from ..agent import YourAgent
from ..types import YourAgentInquiry

@pytest.mark.asyncio
async def test_agent_handles_inquiry():
    """Test agent handles inquiries correctly."""
    # Create mock config
    config = Mock()
    config.name = "test_agent"
    
    # Create agent
    agent = YourAgent(config)
    agent.react_agent = AsyncMock()
    agent.react_agent.process_request.return_value = "Test response"
    
    # Test inquiry handling
    inquiry = YourAgentInquiry(
        query="Test query",
        correlation_id="test-123"
    )
    
    # Process inquiry
    response = await agent.handle_inquiry(inquiry)
    
    # Verify response
    assert response.response == "Test response"
    assert response.correlation_id == "test-123"
```

## Best Practices

### 1. Configuration Management
- Use environment variables for all settings
- Provide sensible defaults
- Validate configuration on startup

### 2. Error Handling
- Always catch and handle exceptions
- Send user-friendly error messages
- Log errors for debugging

### 3. Observability
- Use structured logging
- Implement distributed tracing
- Export metrics for monitoring

### 4. Performance
- Limit concurrent message processing
- Implement timeouts
- Use connection pooling

### 5. Security
- Validate all inputs
- Sanitize outputs
- Use least privilege principle

## Deployment Checklist

- [ ] Agent configuration in `.env`
- [ ] Docker image builds successfully
- [ ] Agent added to `docker-compose.yml`
- [ ] Triage agent routing configured
- [ ] Unit tests passing
- [ ] Integration tests with other agents
- [ ] Monitoring dashboards configured
- [ ] Documentation updated

---

**Previous:** [Multi-Agent Communication](multi-agent-communication.md) | **Next:** [ReAct Framework with DSPy](react-framework-dspy.md)