# RAG with Vespa

## Overview

Retrieval-Augmented Generation (RAG) enhances LLM responses by retrieving relevant documents at runtime. Our implementation uses Vespa for vector search and combines it with agent reasoning.

## Architecture

```
User Query → Policies Agent → Vespa Search → LLM Generation
                ↓
            ReAct Loop
         (reason, search, refine)
```

## Vespa Integration

### Document Schema
```json
{
  "fields": {
    "id": "string",
    "title": "string", 
    "text": "string",
    "category": "string",
    "embedding": "tensor<float>(x[384])"
  }
}
```

### Search Types

| Type | Use Case | Example |
|------|----------|---------|
| **BM25** | Keyword matching | "fire damage coverage" |
| **Vector** | Semantic similarity | "What's covered in floods?" |
| **Hybrid** | Best of both | "home insurance water damage" |

## Agentic RAG Implementation

### 1. Query Analysis
```python
# Agent analyzes intent
if has_policy_number(query):
    use_personal_lookup()
else:
    use_document_search()
```

### 2. Iterative Retrieval
```python
# ReAct agent can search multiple times
results = search_policy_documentation(
    query="fire coverage",
    category="home"
)
if not sufficient(results):
    results += search_policy_documentation(
        query="property damage",
        category="home"
    )
```

### 3. Context Construction
```python
# Build prompt with retrieved chunks
context = "\n".join([r.content for r in results[:5]])
prompt = f"Context:\n{context}\n\nQuestion: {query}"
```

## Configuration

### Chunking Strategy
- **Max tokens**: 500 (fits in context window)
- **Min tokens**: 100 (maintains coherence)
- **Overlap**: 2 sentences (preserves context)

### Retrieval Settings
- **Top K**: 5 documents
- **Score threshold**: 0.7
- **Category filtering**: Optional

## Performance Optimization

1. **Pre-filtering**: Use categories to reduce search space
2. **Caching**: Store frequent queries
3. **Batch processing**: Index documents in parallel
4. **Relevance tuning**: Adjust BM25 weights

## Example Flow

```python
# User: "Does my home insurance cover earthquake damage?"

# 1. Agent reasoning
Thought: General coverage question, search home policies

# 2. Vespa search
Action: search_policy_documentation(
    query="earthquake damage coverage",
    category="home"
)

# 3. Retrieved chunks
Result: [
    "Natural disasters including earthquakes...",
    "Standard policies exclude earthquake damage...",
    "Additional earthquake coverage available..."
]

# 4. Generated response
Response: "Standard home insurance policies typically 
exclude earthquake damage. You would need to purchase 
additional earthquake coverage as a separate policy 
or endorsement."
```

## Monitoring

- **Search latency**: < 100ms target
- **Retrieval accuracy**: Track relevance scores
- **Coverage gaps**: Log queries with no results

---

**Previous:** [Document Ingestion with Temporal](ingestion-pipeline.md) | **Next:** [Vespa Search Guide](vespa-search-guide.md)