# Policies Agent

## Overview

The Policies Agent provides information about insurance policy details, coverage, and terms. It combines **Temporal workflows** for durable document ingestion, **Vespa** for semantic search, and **DSPy ReAct agents** for intelligent policy assistance.

## Key Features

- Retrieves policy details based on policy numbers
- Answers questions about coverage, terms, and policy documents  
- Uses Retrieval Augmented Generation (RAG) with Vespa search
- Enforces strict privacy controls (requires policy numbers)
- References specific documentation sections for detailed answers
- Durable document processing with Temporal workflows

## Architecture

### Core Components

- **Agent Module** (`agent/agent.py`): Main implementation that handles policy-related requests
- **ReAct Implementation** (`agent/react.py`): DSPy ReAct agent with tool calling capabilities  
- **Config** (`config.py`): Configuration settings for the agent
- **Types** (`types.py`): Type definitions for policies data

### Document Ingestion (Temporal)

The document processing pipeline uses Temporal workflows for reliability:
- **Ingestion Workflow** (`ingestion/workflows/ingestion_workflow.py`): Orchestrates document processing
- **Activities** (`ingestion/workflows/activities/`): Four-stage processing pipeline:
  - `document_verification_activity.py`: Checks for existing documents
  - `document_loading_activity.py`: Uses DocLing for PDF/markdown parsing
  - `document_chunking_activity.py`: Hierarchical chunking with overlap
  - `document_indexing_activity.py`: Indexes to Vespa search engine
- **Policy Documents** (`ingestion/documents/`): Contains policy documents for different insurance types

### Search & Retrieval (Vespa)

- **Vespa Integration** (`vespa/`): Search engine configuration and deployment
- **Search Tools** (`agent/tools/retrieval/`): Policy-specific search implementations:
  - `policy_search.py`: Vespa-powered document search
  - `full_document_retrieval.py`: Complete document retrieval
- **Database Tools** (`agent/tools/database/`): Personal policy data access:
  - `policy_data.py`: Policy number-based lookups

### DSPy ReAct Agent

The agent implements intelligent tool selection using DSPy ReAct:

- **ReAct Module** (`agent/react.py`): Core reasoning and tool calling logic
- **Tools**: Two specialized tools for policy operations:
  - `get_personal_policy_details`: Retrieves policy details using policy number
  - `search_policy_documentation`: Searches policy documentation with Vespa

### Optimization

- **SIMBA Optimizer** (`agent/optimization/policies_optimizer_simba.py`): Optimizes prompts for consistent responses
- **Optimized Models** (`agent/optimization/optimized_policies_simba.json`): Pre-trained optimization results

## Technical Details

### Policy Document Structure

The agent handles multiple policy types stored in `ingestion/documents/`:
- Auto insurance (`auto.md`)
- Health insurance (`health.md`) 
- Home insurance (`home.md`)
- Life insurance (`life.md`)

### Data Privacy

The agent implements strict privacy controls:
- Requires valid policy numbers before disclosing information
- Validates user identity based on matching information
- Protects sensitive policy details using appropriate access controls

### Processing Pipeline

1. **Document Ingestion**: Temporal workflow processes documents through verification, loading, chunking, and indexing
2. **Query Analysis**: ReAct agent analyzes user intent (personal vs. general policy questions)
3. **Tool Selection**: Chooses between database lookup or Vespa document search
4. **Information Retrieval**: Executes selected tool to gather relevant information
5. **Response Generation**: DSPy generates contextualized response with specific references

## Development

### Testing

Test the Policies Agent with:
```bash
make test-policies-agent
```

Run retrieval performance tests:
```bash
python -m pytest agents/policies/tests/test_retrieval_performance.py
```

### Document Ingestion

Start the Temporal worker for document processing:
```bash
python agents/policies/ingestion/start_worker.py
```

Ingest new policy documents:
```python
from agents.policies.ingestion.documentation_temporal_client import ingest_document
await ingest_document("path/to/document.pdf", "auto")
```

### Extending

To add support for new policy types:
1. Add policy documents to `ingestion/documents/`
2. Run document ingestion workflow to index new content
3. Add handling for the new policy type in `agent/agent.py`
4. Update category filters in search tools if needed
5. Add test cases for the new policy type

## Integration Points

- **Frontend Agent**: Provides the user interface for policy inquiries
- **Triage Agent**: Routes policy-related questions to this agent
- **Billing Agent**: May cross-reference with policy information
- **Claims Agent**: May need policy details for claims processing

## Documentation

For detailed information about specific components:

- **Document Ingestion**: See [`ingestion/README.md`](ingestion/README.md) for comprehensive Temporal workflow documentation
- **Retrieval Performance**: See [`tests/retrieval_performance/README.md`](tests/retrieval_performance/README.md) for testing and evaluation metrics

## Architecture Highlights

This implementation demonstrates modern AI system design patterns:
- **Temporal Workflows**: Durable, fault-tolerant document processing
- **Vespa Search**: High-performance semantic search with BM25 ranking
- **DSPy ReAct**: Intelligent tool selection and reasoning chains
- **Observability**: Complete tracing with OpenTelemetry
- **Testing**: Comprehensive retrieval performance evaluation with LLM judges