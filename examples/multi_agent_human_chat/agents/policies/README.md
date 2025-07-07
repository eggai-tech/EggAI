# Policies Agent

The Policies Agent provides policy information using RAG (Retrieval-Augmented Generation) to search policy documents.

- **Purpose**: Answers policy coverage questions using RAG
- **Key Features**:
  - Vector-based policy document search
  - Contextual answer generation
  - Multi-document retrieval
  - Vespa-powered search backend
- **API**: Also provides REST API on port 8003

## Quick Start

```bash
# From the project root
make start-policies

# Also start the document ingestion worker
make start-policies-document-ingestion

# Or run directly
python -m agents.policies.agent.main
python -m agents.policies.ingestion.start_worker
```

## Features

- Search policy documentation for coverage information
- Retrieve personal policy details by policy number
- Answer questions about policy terms and conditions
- Category-based filtering (auto, home, health, life)

## Configuration

Key environment variables:
```bash
POLICIES_LANGUAGE_MODEL=lm_studio/gemma-3-12b-it  # Or openai/gpt-4o-mini
POLICIES_PROMETHEUS_METRICS_PORT=9095
POLICIES_VESPA_APP_NAME=policies  # For multi-environment deployments
```

## Document Ingestion

The agent uses Temporal workflows to ingest policy documents:

```bash
# Build the search index
make build-policy-rag-index

# Drop and rebuild index
make drop-vespa-index
make build-policy-rag-index
```

Documents are located in `agents/policies/ingestion/documents/`:
- `auto.md` - Auto insurance policies
- `home.md` - Home insurance policies
- `health.md` - Health insurance policies
- `life.md` - Life insurance policies

## Testing

```bash
# Run all policies tests
make test-policies-agent

# Test retrieval performance
make test-policies-retrieval-performance
```

## Tools

The agent uses ReAct pattern with these tools:

1. **get_personal_policy_details(policy_number: str)**
   - Retrieves specific policy information
   - Returns coverage details, premiums, and status

2. **search_policy_documentation(query: str, category: Optional[str])**
   - Searches indexed policy documents
   - Uses BM25 ranking for relevance
   - Returns contextualized results with citations

## Example Interactions

```
User: "What does my home insurance cover for fire damage?"
Agent: Searches home insurance documents and provides relevant coverage info

User: "What's my deductible for policy H12345?"
Agent: Retrieves personal policy details and provides deductible amount
```

## Development

### Running with Custom Settings

```bash
POLICIES_LANGUAGE_MODEL=openai/gpt-4o-mini \
OPENAI_API_KEY=your-key \
make start-policies
```

### Vespa Configuration

Deploy custom Vespa schema:
```bash
make generate-vespa-package
make deploy-vespa-package
```

### Optimization

Optimize the agent's responses:
```bash
make compile-policies-optimizer
```

## Architecture

- **Channel**: Listens on `agents` channel for `policy_request` messages
- **Output**: Publishes to `human` channel
- **Search**: Uses Vespa for document retrieval
- **Workflow**: Temporal for document processing
- **Streaming**: Supports real-time response streaming

## Monitoring

- Prometheus metrics: http://localhost:9095/metrics
- Temporal UI: http://localhost:8081
- Vespa metrics: http://localhost:19071
- Grafana dashboards: http://localhost:3000