# Agentic RAG Architecture

## Overview

This document describes the Retrieval-Augmented Generation (RAG) system that powers the Policies Agent. The system combines **offline document ingestion** with **online agentic retrieval** to provide accurate, context-aware responses about insurance policies.

## Architecture Overview

```mermaid
graph LR
    subgraph "Offline Stage"
        A[Policy Documents] --> B[Temporal Ingestion Pipeline]
        B --> C[Vespa Search Index]
    end
    
    subgraph "Online Stage"
        D[User Query] --> E[Policies Agent]
        E --> F{Query Analysis}
        F -->|Personal Query| G[Database Lookup]
        F -->|General Query| H[Vespa Retrieval]
        H --> C
        G --> I[Response Generation]
        H --> I
        I --> J[User Response]
    end
```

## Two-Stage Architecture

### 1. Offline Stage: Document Ingestion
[**Full Documentation**: Document Ingestion Pipeline](ingestion-pipeline.md)

- **Temporal-orchestrated** workflow for durability and fault tolerance
- **Document processing**: Loading → Chunking → Embedding → Indexing
- **Storage**: MinIO for document management, Vespa for search
- **Continuous monitoring**: Auto-processes new documents

### 2. Online Stage: Agentic Retrieval

The Policies Agent uses a **ReAct pattern** (Reasoning + Acting) to handle queries:

```python
# Agent's decision flow
if query_needs_personal_data(query):
    # Use database lookup for policy numbers
    result = get_personal_policy_details(policy_number)
else:
    # Use Vespa search for general questions
    result = search_policy_documentation(query, category)
```

## Vespa Search Configuration

### Hybrid Search Strategy

Our system uses **hybrid search** combining semantic and keyword matching:

```yaml
Search Weights:
  - Semantic (Vector): 70%  # Understanding intent
  - Keyword (BM25): 30%     # Exact term matching
```

### Document Schema
[`libraries/integrations/vespa.py`](../libraries/integrations/vespa.py)

```python
{
    "id": "unique_chunk_id",
    "title": "Policy Document - filename.md",
    "text": "chunk content...",
    "category": "home|auto|health|life",
    "embedding": [384-dim vector],
    "metadata": {
        "page_numbers": [1, 2],
        "chunk_index": 0,
        "source_file": "home.md"
    }
}
```

## Key Components

### Agent Tools
[`agents/policies/agent/tools.py`](../agents/policies/agent/tools.py)

1. **`get_personal_policy_details`** - Database lookup for personal policy data
2. **`search_policy_documentation`** - Vespa search for general information

### Retrieval Implementation
[`agents/policies/agent/services/retrieval.py`](../agents/policies/agent/services/retrieval.py)

- Embedding generation using `all-MiniLM-L6-v2`
- Query construction with category filtering
- Result ranking and metadata extraction

### Agent Logic
[`agents/policies/agent/main.py`](../agents/policies/agent/main.py)

- ReAct loop implementation
- Query analysis and tool selection
- Response generation with citations

## Performance & Testing

### Retrieval Performance Test
[**Test Suite**: `test_retrieval_performance.py`](../agents/policies/tests/test_retrieval_performance.py)

Comprehensive 4-stage testing:
1. **Collect** - Query all parameter combinations
2. **Metrics** - Calculate performance statistics
3. **Judge** - LLM evaluation of result quality
4. **Report** - MLflow tracking and analysis

### RAGAS-Style Evaluation
[`agents/policies/tests/retrieval_performance/`](../agents/policies/tests/retrieval_performance/)

Uses [RAGAS](https://docs.ragas.io/)-inspired metrics with custom extensions:
- **LLM Judge**: Answer relevancy, completeness, faithfulness (40% weight)
- **Context Metrics**: Recall, Precision@K, NDCG (20% weight)
- **Retrieval Metrics**: Success rate, speed, hit count (30% weight)  
- **Position Metrics**: Best match position, top-3 hit rate (10% weight)

Results tracked in MLflow for continuous optimization.

## User Flow: Chat UI to RAG

### How Users Access Policy Information

1. **User Opens Chat UI**
   ```
   http://localhost:8501
   ```

2. **User Asks Policy Question**
   ```
   User: "What is the deductible for auto insurance?"
   ```

3. **Frontend Routes to Policies Agent**
   - Triage agent classifies query → routes to Policies Agent
   - Policies Agent analyzes query type

4. **Agent Retrieves Information**
   ```python
   # For general questions → Vespa search
   "What is covered?" → search_policy_documentation()
   
   # For personal data → Database lookup  
   "My policy A12345" → get_personal_policy_details()
   ```

5. **Response with Citations**
   ```
   Agent: "For auto insurance, the standard deductible is $500 
   for collision coverage and $250 for comprehensive coverage.
   
   Source: Auto Policy Document, Section 3.5"
   ```

### Quick Start
```bash
# 1. Start everything
make docker-up && make start-all

# 2. Open chat UI
open http://localhost:8501

# 3. Ask policy questions
# Examples:
# - "What's covered under home insurance?"
# - "How do I file a claim?"
# - "What are the life insurance exclusions?"
```

## Configuration

### Search Parameters
```python
# agents/policies/agent/config.py
hybrid_alpha = 0.7  # 70% semantic, 30% keyword
max_results = 5     # Top K results
min_score = 0.7     # Relevance threshold
```

### Model Settings
```python
# Embedding model for search
embedding_model = "all-MiniLM-L6-v2"  # 384 dimensions
embedding_size = 384

# LLM for response generation
language_model = "gpt-4o-mini"
```

## Related Documentation

- [Document Ingestion Pipeline](ingestion-pipeline.md) - Offline stage details
- [Building Agents Guide](building-agents-eggai.md) - Agent development patterns
- [Vespa Schema](../agents/policies/vespa/schema/) - Search configuration

---

**Previous:** [Building Agents Guide](building-agents-eggai.md) | **Next:** [Document Ingestion Pipeline](ingestion-pipeline.md)