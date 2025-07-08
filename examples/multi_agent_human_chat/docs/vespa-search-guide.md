# Vespa Search Guide

This guide explains how to work with Vespa to explore policy data and utilize different search capabilities.

## Overview

The system uses Vespa as a search engine with support for:

- **Keyword search** - Traditional BM25 text matching
- **Vector search** - Semantic similarity using embeddings
- **Hybrid search** - Combines keyword and vector search

## Accessing Vespa

### Vespa Web Interface

- **URL**: http://localhost:19071
- **Query endpoint**: http://localhost:8080/search/

### REST API (via Policies Agent)

- **URL**: http://localhost:8003
- **Endpoints**: `/search`, `/documents`, `/categories`

## Search Types

### 1. Keyword Search (BM25)

Traditional text matching using BM25 ranking.

```bash
# Direct Vespa query
curl -X POST http://localhost:8080/search/ \
  -d '{
    "yql": "select * from policy_document where text contains \"fire damage\"",
    "ranking": "default"
  }'

# Via Policies API
curl -X POST http://localhost:8003/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "fire damage coverage",
    "search_type": "keyword",
    "max_hits": 5
  }'
```

### 2. Vector Search (Semantic)

Uses embeddings to find semantically similar content.

```bash
# Via Policies API (handles embedding generation)
curl -X POST http://localhost:8003/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What is covered if my house burns down?",
    "search_type": "vector",
    "max_hits": 5
  }'
```

### 3. Hybrid Search

Combines keyword and vector search with configurable weighting.

```bash
# Via Policies API (default alpha=0.7)
curl -X POST http://localhost:8003/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "fire damage coverage home insurance",
    "search_type": "hybrid",
    "max_hits": 10
  }'
```

## Ranking Profiles

### Available Profiles

1. **default** - Standard BM25 text ranking

   ```python
   nativeRank(title, text)
   ```

2. **with_position** - Considers chunk position (earlier chunks ranked higher)

   ```python
   nativeRank(title, text) * (1.0 - 0.3 * attribute(chunk_position))
   ```

3. **semantic** - Pure vector similarity

   ```python
   closeness(field, embedding)
   ```

4. **hybrid** - Weighted combination (alpha controls balance)

   ```python
   (1.0 - alpha) * nativeRank + alpha * closeness
   ```

## Exploring Data

### List All Documents

```bash
# Get all documents
curl "http://localhost:8003/documents"

# Get documents by category
curl "http://localhost:8003/documents?category=home"
```

### Search with Filters

```bash
# Search within a category
curl -X POST http://localhost:8003/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "deductible",
    "category": "auto",
    "search_type": "hybrid"
  }'
```

### Get Document Categories

```bash
curl "http://localhost:8003/categories"
```

## Advanced Queries

### Direct YQL Queries

For complex queries, use Vespa's YQL (Yahoo Query Language):

```bash
# Search with specific fields
curl -X POST http://localhost:8080/search/ \
  -d '{
    "yql": "select * from policy_document where title contains \"coverage\" and category = \"home\"",
    "hits": 10
  }'

# Wildcard search
curl -X POST http://localhost:8080/search/ \
  -d '{
    "yql": "select * from policy_document where text matches \"fire.*damage\"",
    "ranking": "default"
  }'
```

### Debugging Search Results

```bash
# Get detailed scoring information
curl -X POST http://localhost:8080/search/ \
  -d '{
    "yql": "select * from policy_document where text contains \"fire\"",
    "ranking": "default",
    "trace.level": 5,
    "hits": 3
  }'
```

## Schema Details

### Document Fields

- `id` - Unique document identifier
- `title` - Document title (searchable)
- `text` - Main content (searchable)
- `category` - Document category (home, auto, life, health)
- `chunk_index` - Position in original document
- `chunk_position` - Normalized position (0-1)
- `source_file` - Original file name
- `page_range` - Page numbers in source
- `embedding` - 384-dimensional vector

### Indexing Configuration

- Text fields use BM25 indexing
- Embeddings use HNSW index for fast similarity search
- Categories are attributes for filtering

## Performance Tips

1. **Use appropriate search type**:
   - Keyword: Fast, exact matching
   - Vector: Slower, semantic understanding
   - Hybrid: Balanced performance

2. **Limit results**: Use `max_hits` to control response size

3. **Filter by category**: Reduces search space significantly

4. **Monitor Vespa metrics**: http://localhost:19071/state/v1/metrics

## Troubleshooting

### No Results

```bash
# Check document count
curl "http://localhost:8080/search/?yql=select * from policy_document | all()"

# Verify indexing completed
make start-policies-document-ingestion
```

### Slow Queries

- Check Vespa resource usage
- Consider using keyword search for simple queries
- Reduce `max_hits` parameter

### Embedding Errors

- Ensure embedding model is loaded
- Check vector dimensions (must be 384)

## Examples

### Finding Specific Coverage

```bash
# What does home insurance cover for water damage?
curl -X POST http://localhost:8003/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "water damage flood coverage exclusions",
    "category": "home",
    "search_type": "hybrid",
    "max_hits": 5
  }'
```

### Comparing Policies

```bash
# Get all deductible information across categories
curl -X POST http://localhost:8003/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "deductible amount payment",
    "search_type": "keyword",
    "max_hits": 20
  }'
```

## Related Documentation

- [Ingestion Pipeline](ingestion-pipeline.md) - How documents are indexed
- [Retrieval Performance Testing](retrieval-performance-testing.md) - Search quality metrics
- Vespa Documentation: https://docs.vespa.ai

---

**Previous:** [RAG with Vespa](agentic-rag.md) | **Next:** [Agent & Prompt Optimization](advanced-topics/agent-optimization.md)
