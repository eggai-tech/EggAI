# Policies Agent

An intelligent insurance policy agent that provides policy information and answers coverage questions using RAG (Retrieval Augmented Generation).

## Quick Start

### 1. Start the Agent
```bash
# Run the API server
python -m agents.policies.agent.main policies-agent 8003

# Or run the agent directly
python -m agents.policies.agent
```

### 2. Start Document Ingestion Worker (if needed)
```bash
python agents/policies/ingestion/start_worker.py
```

### 3. Test the Agent
```bash
make test-policies-agent
```

## What It Does

- **Personal Policy Lookup**: Retrieves policy details using policy numbers (requires authentication)
- **Coverage Questions**: Answers questions about what's covered in different policy types
- **Document Search**: Searches through policy documentation using semantic search (Vespa)
- **Privacy Protection**: Enforces strict access controls for personal information

## Key Components

### Core Files
- `agent/agent.py` - Main agent implementation
- `agent/reasoning.py` - DSPy ReAct reasoning logic
- `agent/main.py` - FastAPI server
- `agent/api/` - REST API endpoints and models

### Tools
- `get_personal_policy_details` - Retrieves specific policy information
- `search_policy_documentation` - Searches policy documents

### Services
- `services/search_service.py` - Handles document search
- `services/document_service.py` - Manages document operations
- `services/reindex_service.py` - Handles reindexing
- `services/embeddings.py` - Generates embeddings for semantic search

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/kb/documents` | GET | List all documents |
| `/api/v1/kb/search` | GET | Search documents |
| `/api/v1/kb/vector-search` | POST | Semantic search |
| `/api/v1/kb/reindex` | POST | Reindex documents |
| `/api/v1/health` | GET | Health check |

## Configuration

Key environment variables:
```bash
VESPA_ENDPOINT=http://localhost:8080
TEMPORAL_ENDPOINT=localhost:7233
OTEL_ENDPOINT=http://localhost:4317
POLICIES_USE_OPTIMIZED_PROMPTS=false  # Use SIMBA-optimized prompts
```

## Development

### Run Tests
```bash
# All tests with coverage
python agents/policies/run_coverage.py

# Specific test suites
pytest agents/policies/tests/test_api_integration.py -v
pytest agents/policies/tests/test_services.py -v
```

### Add New Policy Types
1. Add document to `ingestion/documents/`
2. Run ingestion workflow
3. Update category validation if needed

### Optimize Agent Responses
```bash
# Run SIMBA optimization
python -m agents.policies.agent.optimization.policies_optimizer_simba
```

## Architecture

```
User Query → Triage Agent → Policies Agent
                                ↓
                          ReAct Reasoning
                                ↓
                    Tool Selection (Database or Search)
                                ↓
                          Response Generation
```

## Integration

Works with:
- **Triage Agent**: Routes policy questions here
- **Claims Agent**: May reference policy details
- **Billing Agent**: Cross-references policy information

## Troubleshooting

- **No search results**: Check if documents are indexed (`/api/v1/kb/indexing-status`)
- **Slow responses**: Verify Vespa is running and accessible
- **Missing policy data**: Ensure Temporal worker is running for ingestion

## More Information

- [Document Ingestion Details](ingestion/README.md)
- [Performance Testing](tests/retrieval_performance/README.md)