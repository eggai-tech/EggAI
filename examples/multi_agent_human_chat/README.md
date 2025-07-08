# Multi-Agent Insurance Support System

[![Quality Gate Status](https://sonarcloud.io/api/project_badges/measure?project=eggai-tech_EggAI&metric=alert_status)](https://sonarcloud.io/summary/new_code?id=eggai-tech_EggAI)

A multi-agent system where AI agents collaborate to provide personalized insurance support. Features billing inquiries, claims processing, policy information retrieval (RAG), and intelligent routing.

![Chat UI Screenshot](https://raw.githubusercontent.com/eggai-tech/EggAI/refs/heads/main/docs/docs/assets/support-chat.png)

> **Note:** Runs completely locally with LM Studio - no cloud services or API keys required!

## Quick Start

### Prerequisites

- **Python** 3.11+
- **Docker** and **Docker Compose**
- **LM Studio** (for local models) or OpenAI API key (for cloud models)

### 1. Setup

```bash
# Clone the repository
git clone git@github.com:eggai-tech/EggAI.git
cd examples/multi_agent_human_chat

# Create virtual environment and install dependencies
make setup
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Copy environment configuration
cp .env.example .env

# (Optional) Configure Guardrails for content moderation
# guardrails configure --token $GUARDRAILS_TOKEN
# guardrails hub install hub://guardrails/toxic_language
```

### 2. Configure Language Models

#### Option A: Local Models (Default - No API Keys Required)

1. Download and install [LM Studio](https://lmstudio.ai/)
2. Launch LM Studio and load a compatible model (e.g., gemma-3-12b-it-qat)
3. Start the local server (should run on http://localhost:1234)

#### Option B: OpenAI Models

Edit `.env` and uncomment the OpenAI model lines for every agent:

```bash
# Uncomment these lines in .env
# TRIAGE_LANGUAGE_MODEL_API_BASE=https://api.openai.com/v1
# TRIAGE_LANGUAGE_MODEL=openai/gpt-4o-mini
# OPENAI_API_KEY=your-api-key-here
[...]
```

### 3. Start Platform Services

```bash
make docker-up  # Start all required services (Kafka, Vespa, Temporal, etc.)
```

All services are accessible directly from the chat UI header, or you can open them individually via their URLs:

| Service     | Local URL                            | Description                            | Product URL                              |
|-------------|--------------------------------------|----------------------------------------|-------------------------------------------|
| Redpanda    | [http://localhost:8082](http://localhost:8082)   | Kafka-compatible message queue         | [redpanda.com](https://redpanda.com)       |
| Vespa       | [http://localhost:19071](http://localhost:19071) | Vector search engine and ranking       | [vespa.ai](https://vespa.ai)               |
| Temporal    | [http://localhost:8081](http://localhost:8081)   | Orchestration engine for workflows     | [temporal.io](https://temporal.io)         |
| MLflow      | [http://localhost:5001](http://localhost:5001)   | Machine learning experiment tracking   | [mlflow.org](https://mlflow.org)           |
| Grafana     | [http://localhost:3000](http://localhost:3000)   | Visualization and dashboarding tool    | [grafana.com](https://grafana.com)         |
| Prometheus  | [http://localhost:9090](http://localhost:9090)   | Metrics collection and time-series DB  | [prometheus.io](https://prometheus.io)     |

## Run the System

```bash
make start-all
```

**Open http://localhost:8000 to start chatting!**

The chat interface includes example questions to get started:

- **Support categories** with clickable example questions
- **Policy Inquiries** - Coverage and policy details
- **Billing & Payments** - Premiums and payment info  
- **Claims Support** - File claims and check status
- **General Support** - Escalations and other help

### Usage

You can also interact with the system using free-form natural language.  
Simply type your request into the chat input at the bottom of the interface.

Here are some example prompts you can try:

- _"What's my premium for policy B67890?"_
- _"I want to file a claim"_
- _"What does my home insurance cover?"_
- _"I have a complaint about my service"_

The system will automatically route your request to the appropriate agent.

To get a general understanding of how the system works, please review the [_System Workflow Overview_](docs/simple_example_flow.md).

## Documentation

- [System Architecture](docs/system-architecture.md)
- [Agent Capabilities Overview](docs/agents-overview.md)
- [Multi-Agent Communication](docs/multi-agent-communication.md)
- [Building Agents Guide](docs/building-agents-eggai.md)
- [ReAct Framework with DSPy](docs/react-framework-dspy.md)
- [Document Ingestion with Temporal](docs/ingestion-pipeline.md)
- [RAG with Vespa](docs/agentic-rag.md)
- [Vespa Search Guide](docs/vespa-search-guide.md)
- [Agent & Prompt Optimization](docs/advanced-topics/agent-optimization.md)
- [Deployment Guide](docs/advanced-topics/multi-environment-deployment.md)

## Development

### Testing

```bash
make test        # Run all tests
make lint        # Check code quality
make format      # Format code
```
