# Policies Agent

RAG-powered policy information search and retrieval with Temporal workflows and Vespa hybrid search.

## Documentation

- [Agentic RAG Architecture](../../docs/agentic-rag.md) - ReAct pattern implementation  
- [Ingestion Pipeline](../../docs/ingestion-pipeline.md) - Temporal workflows and document processing
- [Vespa Search Guide](../../docs/vespa-search-guide.md) - Hybrid search configuration
- [Retrieval Performance Testing](../../docs/retrieval-performance-testing.md) - Benchmarking guide

## What it does
- Searches policy documents using hybrid search (vector + keyword)
- Retrieves personal policy details by policy number
- Answers questions about terms and conditions with citations
- Supports auto, home, health, life insurance categories
- Uses ReAct pattern for intelligent tool selection

## Architecture Overview

### Core Components
- **Temporal Workflows**: Reliable document ingestion pipeline
- **Vespa Search**: Hybrid search combining vector similarity (70%) and keyword matching (30%)
- **DSPy ReAct**: Intelligent tool selection and query planning
- **MinIO Storage**: Document and artifact management

### Key Features
- **Two-Stage Architecture**: Offline ingestion + Online retrieval
- **Enhanced Metadata**: Page numbers, headings, citations, chunk relationships
- **Multiple Ranking Profiles**: Default, semantic, hybrid, with_position
- **Performance Tested**: RAGAS-style metrics with automated benchmarking

## Quick Start
```bash
# Start services
make start-policies
make start-policies-document-ingestion  # Required for document processing

# Build search index
make build-policy-rag-index

# Run tests
make test-policies-agent
```

## Configuration
```bash
# Language model selection
POLICIES_LANGUAGE_MODEL=openai/gpt-4o-mini  # Or lm_studio/gemma-3-12b-it

# Vespa endpoints
VESPA_CONFIG_URL=http://localhost:19071
VESPA_QUERY_URL=http://localhost:8080

# Temporal settings
TEMPORAL_SERVER_URL=localhost:7233
TEMPORAL_NAMESPACE=default
```

## Tools
- `get_personal_policy_details(policy_number)` - Returns coverage, premiums, status for personal policies
- `search_policy_documentation(query, category)` - Hybrid search with citations and relevance scoring

## Document Management
```bash
make build-policy-rag-index  # Build search index
```


## Testing
```bash
make test-policies-agent
make test-policies-retrieval-performance
```

## API Examples

### Search Documentation
```bash
curl -X POST http://localhost:8001/api/v1/kb/search/vector \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What is covered under collision damage?",
    "category": "auto",
    "max_hits": 5,
    "search_type": "hybrid"
  }'
```

### Direct Agent Query
```python
from agents.policies.agent import PoliciesAgent

agent = PoliciesAgent()
response = agent.process_message(
    "What does my auto policy POL-AUTO-123456 cover?"
)
```

## Related Documentation
- [System Architecture](../../docs/system-architecture.md)
- [Building Agents Guide](../../docs/building-agents-eggai.md)
- [Multi-Agent Communication](../../docs/multi-agent-communication.md)
- [Performance Testing](../../docs/retrieval-performance-testing.md)