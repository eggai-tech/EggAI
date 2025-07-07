# Policies Agent

RAG-powered policy information search and retrieval.

## What it does
- Searches policy documents for coverage information
- Retrieves personal policy details by policy number
- Answers questions about terms and conditions
- Supports auto, home, health, life categories

## Quick Start
```bash
make start-policies
make start-policies-document-ingestion  # Also needed for document processing
```

## Configuration
```bash
POLICIES_LANGUAGE_MODEL=lm_studio/gemma-3-12b-it  # Or openai/gpt-4o-mini
```

## Tools
- `get_personal_policy_details(policy_number)` - Returns coverage, premiums, status
- `search_policy_documentation(query, category)` - BM25 search with citations

## Document Management
```bash
make build-policy-rag-index  # Build search index
```

Documents in `agents/policies/ingestion/documents/`:
- `auto.md`, `home.md`, `health.md`, `life.md`

## Testing
```bash
make test-policies-agent
make test-policies-retrieval-performance
```