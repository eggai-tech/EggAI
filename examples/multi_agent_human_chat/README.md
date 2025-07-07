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
Edit `.env` and uncomment the OpenAI model lines:
```bash
# Uncomment these lines in .env
# TRIAGE_LANGUAGE_MODEL=openai/gpt-4o-mini
# OPENAI_API_KEY=your-api-key-here
```

### 3. Start Platform Services

```bash
make docker-up  # Start all required services (Kafka, Vespa, Temporal, etc.)
```

### 4. Run the System

```bash
make start-all
```

Open http://localhost:8000 to start chatting!

The chat interface now includes:
- **Support categories** with clickable example questions
- **Policy Inquiries** - Coverage and policy details
- **Billing & Payments** - Premiums and payment info  
- **Claims Support** - File claims and check status
- **General Support** - Escalations and other help

Just click any example question to get started!

**Example queries:**
- "What's my premium for policy B67890?"
- "I want to file a claim"
- "What does my home insurance cover?"
- "I have a complaint about my service"

**Platform Services:**
All services are accessible directly from the chat UI header, or visit:
- Chat UI: http://localhost:8000
- Admin Dashboard: http://localhost:8000/admin.html - System monitoring
- Redpanda Console: http://localhost:8082 - Message queue monitoring
- Temporal UI: http://localhost:8081 - Workflow management
- Grafana: http://localhost:3000 - Metrics & dashboards
- MLflow: http://localhost:5001 - ML experiment tracking
- Vespa Status: http://localhost:19071 - Search engine status
- Prometheus: http://localhost:9090 - Metrics collection

## System Overview

![Architecture](https://raw.githubusercontent.com/eggai-tech/EggAI/refs/heads/main/docs/docs/assets/architecture-multi-agent-insurance-support-system.svg)

**Specialized Agents:**
- **Frontend** - WebSocket gateway for user connections
- **Triage** - ML-based routing to appropriate agents
- **Billing** - Payment inquiries and premium information
- **Claims** - Claims status and filing
- **Policies** - RAG-powered policy document search
- **Escalation** - Complex issues and complaints
- **Audit** - Compliance logging

**Infrastructure:** Redpanda (Kafka), Vespa (Vector Search), Temporal (Workflows), MLflow, Grafana, Prometheus

## Testing

```bash
make test        # Run all tests
make lint        # Check code quality
make format      # Format code
```

## Documentation

- [System Architecture](docs/system-architecture.md) - High-level design, component interactions, and communication flow
- [Agent Overview](docs/agents-overview.md) - Detailed agent descriptions and testing guide
- [UI Enhancements](docs/ui-enhancements.md) - Support categories and example questions
- [Ingestion Pipeline](docs/ingestion-pipeline.md) - Temporal workflows and Vespa integration
- [Vespa Search Guide](docs/vespa-search-guide.md) - Search types, ranking profiles, and data exploration
- [Model Training](docs/model-training.md) - Custom classifier training guide
- [Retrieval Performance Testing](docs/retrieval-performance-testing.md) - Evaluation metrics and benchmarks
- [Advanced Topics](docs/advanced-topics.md) - Multi-environment deployment, optimization, and training

## Advanced Topics

### Multi-Environment Deployment

Run multiple isolated instances using deployment namespaces:

```bash
export DEPLOYMENT_NAMESPACE=pr-123  # or staging, prod, etc.
make start-all
```

This prefixes Kafka topics, Temporal namespaces, and Vespa app names.

### Agent Optimization

```bash
make compile-billing-optimizer   # Optimize billing agent
make compile-all                # Optimize all agents
```

### Custom Model Training

```bash
make train-triage-classifier-v3  # Train baseline classifier
make train-triage-classifier-v5  # Train attention-based classifier
```

View results in MLflow at http://localhost:5001

## Cleaning Up

```bash
make docker-down  # Stop infrastructure
make clean       # Remove virtual environment
```