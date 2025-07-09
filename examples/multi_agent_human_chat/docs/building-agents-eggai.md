# Building Agents Guide

Build a GDPR agent using DSPy ReAct in 5 minutes.

## Step 1: Create the Agent Structure

```bash
mkdir -p agents/gdpr
cd agents/gdpr
```

## Step 2: Create Configuration File

Create `config.py`:

```python
from pydantic import Field
from libraries.core import BaseAgentConfig

class Settings(BaseAgentConfig):
    app_name: str = Field(default="gdpr_agent")
    prometheus_metrics_port: int = Field(default=9099)

settings = Settings()
```

## Step 3: Create the Agent

Create `agent.py`:

```python
import dspy
from eggai import Agent, Channel
from libraries.observability.tracing import TracedMessage, TracedReAct, create_tracer
from libraries.observability.logger import get_console_logger
from libraries.communication.channels import channels
from libraries.communication.messaging import subscribe

logger = get_console_logger("gdpr_agent")
agents_channel = Channel(channels.agents)
human_stream_channel = Channel(channels.human_stream)

# Define message types
class GDPRInquiry(TracedMessage):
    type: str = "GDPRInquiry"
    query: str

class GDPRResponse(TracedMessage):
    type: str = "GDPRResponse"
    answer: str

# Sample GDPR data
GDPR_ARTICLES = {
    "17": {
        "title": "Right to erasure ('right to be forgotten')",
        "content": "The data subject shall have the right to obtain from the controller the erasure of personal data..."
    },
    "33": {
        "title": "Notification of a personal data breach",
        "content": "In case of a personal data breach, the controller shall notify within 72 hours..."
    }
}

# Define tools for ReAct
def list_gdpr_articles() -> str:
    """List all GDPR article numbers and titles."""
    articles_list = []
    for num, data in sorted(GDPR_ARTICLES.items(), key=lambda x: int(x[0])):
        articles_list.append(f"Article {num}: {data['title']}")
    return "GDPR Articles:\n" + "\n".join(articles_list)

def read_gdpr_article(article_number: str) -> str:
    """Read a specific GDPR article content."""
    if article_number in GDPR_ARTICLES:
        article = GDPR_ARTICLES[article_number]
        return f"Article {article_number}: {article['title']}\n\n{article['content']}"
    return f"Article {article_number} not found"

# Tools for ReAct
TOOLS = [list_gdpr_articles, read_gdpr_article]

# Create ReAct signature
class GDPRSignature(dspy.Signature):
    """Answer GDPR-related questions."""
    query: str = dspy.InputField(desc="The GDPR question")
    answer: str = dspy.OutputField(desc="Answer based on GDPR knowledge")

# Initialize agent
gdpr_agent = Agent(name="gdpr")

# Create ReAct agent
tracer = create_tracer("gdpr_agent")
react = TracedReAct(
    signature=GDPRSignature,
    tools=TOOLS,
    tracer=tracer,
    max_iters=3
)

@subscribe(
    agent=gdpr_agent,
    channel=agents_channel,
    filter_func=lambda msg: msg.get("type") == "GDPRInquiry",
    group_id="gdpr_group"
)
async def handle_gdpr_inquiry(message: TracedMessage):
    """Handle GDPR inquiries using ReAct."""
    query = message.data.get("query", "")
    logger.info(f"Processing: {query[:50]}...")
    
    # Use ReAct to answer the query
    result = react(query=query)
    
    # Send response
    await human_stream_channel.publish(
        TracedMessage(
            type="agent_message",
            source="GDPR",
            data={
                "message": result.answer,
                "connection_id": message.data.get("connection_id", "unknown"),
                "agent": "GDPR"
            },
            traceparent=message.traceparent,
            tracestate=message.tracestate
        )
    )
    
    logger.info("Response sent.")
```

## Step 4: Create Main Entry Point

Create `main.py`:

```python
import asyncio
from eggai import eggai_main
from eggai.transport import eggai_set_default_transport
from libraries.communication.transport import create_kafka_transport
from libraries.observability.logger import get_console_logger
from libraries.observability.tracing import init_telemetry
from libraries.ml.dspy.language_model import dspy_set_language_model
from .config import settings
from .agent import gdpr_agent

eggai_set_default_transport(
    lambda: create_kafka_transport(
        bootstrap_servers=settings.kafka_bootstrap_servers,
        ssl_cert=settings.kafka_ca_content,
    )
)

logger = get_console_logger("gdpr_agent")

@eggai_main
async def main():
    logger.info(f"Starting {settings.app_name}")
    
    init_telemetry(app_name=settings.app_name, endpoint=settings.otel_endpoint)
    dspy_set_language_model(settings)
    
    await gdpr_agent.start()
    logger.info(f"{settings.app_name} started successfully")
    
    await asyncio.Future()  # Keep running

if __name__ == "__main__":
    asyncio.run(main())
```

## Step 5: Create Module Init

Create `__init__.py`:

```python
# GDPR Agent Module
```

## Step 6: Create a Test

Create `test.py`:

```python
import asyncio
from eggai import Agent, Channel
from eggai.transport import eggai_set_default_transport
from libraries.communication.transport import create_kafka_transport
from libraries.communication.channels import channels
from libraries.observability.tracing import TracedMessage

eggai_set_default_transport(
    lambda: create_kafka_transport(bootstrap_servers="localhost:19092")
)

async def test():
    test_agent = Agent("test")
    agents_channel = Channel(channels.agents)
    
    await test_agent.start()
    
    # Send test query
    await agents_channel.publish(
        TracedMessage(
            type="GDPRInquiry",
            source="test",
            data={
                "query": "What is the right to be forgotten?",
                "connection_id": "test-connection"
            }
        )
    )
    
    await asyncio.sleep(2)
    await test_agent.stop()
    print("Test completed!")

if __name__ == "__main__":
    asyncio.run(test())
```

## Step 7: Update Makefile

Add these lines to your project's Makefile:

```makefile
start-gdpr:
	@echo "Starting GDPR Agent..."
	@source $(VENV_DIR)/bin/activate && $(VENV_DIR)/bin/python -m agents.gdpr.main

test-gdpr:
	@echo "Testing GDPR Agent..."
	@source $(VENV_DIR)/bin/activate && $(VENV_DIR)/bin/python -m agents.gdpr.test
```

## Step 8: Run Your Agent

1. Start the agent:
```bash
make start-gdpr
```

2. In another terminal, run the test:
```bash
make test-gdpr
```

## What You Built

A minimal GDPR agent with:
- **ReAct reasoning**: DSPy framework handles the thinking process
- **Two simple tools**: List articles and read specific articles
- **Kafka messaging**: Integrates with the multi-agent system
- **Ready to extend**: Add more GDPR articles or fetch from real sources

## Next Steps

To integrate with the main system:
1. Add your message type to the triage agent's routing logic
2. Deploy alongside other agents
3. Extend with real GDPR data sources

---

**Previous:** [Multi-Agent Communication](multi-agent-communication.md) | **Next:** [ReAct Framework with DSPy](react-framework-dspy.md)