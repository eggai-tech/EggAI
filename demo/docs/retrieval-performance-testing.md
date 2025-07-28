# Retrieval Performance Testing Guide

This guide walks you through testing and optimizing the retrieval performance of your RAG system.

## Quick Start

### 1. Run Your First Test

```bash
# Start infrastructure
make docker-up

# Run basic performance test (5 test cases)
LIMIT_DATASET_ITEMS=5 pytest agents/policies/tests/test_retrieval_performance.py -v

# OR run it via
make test-policies-retrieval-performance
```

### 2. View Results

```bash
# Check console output for best configuration
# Look for: "BEST PERFORMING COMBINATION"

# View detailed metrics in MLflow
open http://localhost:5001
# Navigate to: Experiments → retrieval_performance_evaluation
```

## Understanding the Test

### What It Tests

The test evaluates different search configurations to find the optimal settings:

```
Search Types:  hybrid, keyword, vector
Max Results:   1, 5, 10
Test Cases:    Real Q&A pairs from policy documents
```

### Test Stages

1. **Setup** - Deploys Vespa schema and ingests documents
2. **Collect** - Runs all parameter combinations
3. **Metrics** - Calculates performance statistics
4. **Judge** - Optional LLM quality evaluation (RAGAS-style)
5. **Report** - Logs to MLflow and recommends best config

### RAGAS Integration

This test uses [RAGAS](https://docs.ragas.io/)-inspired evaluation:
- **Answer Relevancy**: How well retrieved chunks answer the question
- **Faithfulness**: Whether the content supports the answer
- **Context Precision**: Quality of retrieved context ranking

The LLM judge (GPT-4o-mini) evaluates each retrieval result against expected answers.

## Practical Examples

### Example 1: Quick Performance Check

```bash
# Test with minimal dataset for quick feedback
LIMIT_DATASET_ITEMS=2 pytest agents/policies/tests/test_retrieval_performance.py::test_retrieval_performance -s

# Expected output:
# BEST PERFORMING COMBINATION
# Search Type: HYBRID
# Max Hits: 5
# Final Score: 0.845
# RECOMMENDATION: Excellent overall performance!
```

### Example 2: Test Without LLM Judge

```python
# In test_retrieval_performance.py, modify the config:
config = RetrievalTestConfiguration(
    search_types=["hybrid", "keyword"],  # Skip vector for speed
    max_hits_values=[5, 10],             # Test fewer options
    enable_llm_judge=False               # No OpenAI API needed
)
```

### Example 3: Test Specific Search Type

```python
# Test only hybrid search with different hit counts
config = RetrievalTestConfiguration(
    search_types=["hybrid"],
    max_hits_values=[1, 3, 5, 10, 20],
    enable_llm_judge=True
)
```

## Reading the Results

### Console Output

```
BEST PERFORMING COMBINATION (WITH LLM JUDGE)
============================================================
Search Type: HYBRID
Max Hits: 5
Final Score: 0.812

Key Metrics:
  • Success Rate: 100.0%
  • Avg Retrieval Time: 87.3ms      ← Fast response
  • Avg Quality Score: 0.854         ← High quality
  • Pass Rate: 92.0%                 ← Most queries pass
  • Hit Rate Top 3: 88.0%            ← Good ranking
============================================================
RECOMMENDATION: Excellent overall performance!
```

### Evaluation Metrics (RAGAS-Inspired)

Our evaluation uses RAGAS-style metrics plus custom retrieval metrics:

#### Retrieval Metrics (30% weight)
- **Success Rate** (15%): % of queries returning results without errors
- **Avg Total Hits** (10%): Documents retrieved per query
- **Avg Retrieval Time** (5%): Response speed in ms (target < 100ms)

#### LLM Judge Metrics (40% weight)
- **Quality Score** (20%): Overall relevance rating (0-1)
- **Pass Rate** (15%): % of queries scoring ≥ 0.7
- **Completeness** (5%): How fully the answer addresses the question

#### Context Metrics (20% weight)
- **Recall** (8%): Whether relevant context was found
- **Precision@K** (7%): Accuracy of top K results
- **NDCG** (5%): Ranking quality (Normalized Discounted Cumulative Gain)

#### Position Metrics (10% weight)
- **Best Position** (5%): Where the best match appears
- **Hit Rate Top 3** (5%): % with relevant result in top 3

**Final Score**: Weighted sum of all metrics (0-1 scale). Scores > 0.8 = Excellent.

## Common Scenarios

### Scenario 1: "My retrieval is too slow"

```python
# Focus on speed metrics
config = RetrievalTestConfiguration(
    search_types=["keyword", "hybrid"],  # Skip pure vector
    max_hits_values=[1, 5],              # Fewer results
    enable_llm_judge=False               # Speed test only
)
```

### Scenario 2: "Results aren't relevant"

```python
# Focus on quality with LLM judge
config = RetrievalTestConfiguration(
    search_types=["hybrid", "vector"],   # Semantic search
    max_hits_values=[5, 10, 20],         # More results
    enable_llm_judge=True                # Quality focus
)
```

### Scenario 3: "Need to optimize for production"

```bash
# Run full test suite
make test-policies-retrieval-performance

# Check MLflow for trends
# Look for configuration with best balance of:
# - High quality score (> 0.8)
# - Fast retrieval (< 100ms)
# - Consistent pass rate (> 80%)
```

## Customization

### Add Test Questions
`agents/policies/tests/retrieval_performance/filtered_qa_pairs.json`

### Adjust Metric Weights  
`agents/policies/tests/retrieval_performance/metrics_config.py`

### Test New Documents
1. Add to `agents/policies/ingestion/documents/`
2. Update test questions
3. Run test (auto-ingests)

## Troubleshooting

### "Test times out"

```bash
# Increase timeout or reduce test size
LIMIT_DATASET_ITEMS=3 pytest agents/policies/tests/test_retrieval_performance.py
```

### "No MLflow results"

```bash
# Check MLflow is running
docker ps | grep mlflow

# Restart if needed
docker-compose restart mlflow
```

### "Low quality scores"

1. Check document ingestion completed
2. Verify test questions match document content
3. Try hybrid search with more results (10-20)

## Next Steps

1. **Run baseline test** to understand current performance
2. **Identify bottlenecks** using metrics
3. **Test variations** to find optimal config
4. **Apply best config** to production
5. **Monitor continuously** with MLflow

## Code References

### Core Files
- [`test_retrieval_performance.py`](../agents/policies/tests/test_retrieval_performance.py) - Main test
- [`metrics_config.py`](../agents/policies/tests/retrieval_performance/metrics_config.py) - Metric definitions
- [`llm_judge.py`](../agents/policies/tests/retrieval_performance/llm_judge.py) - RAGAS-style evaluation
- [`context_metrics.py`](../agents/policies/tests/retrieval_performance/context_metrics.py) - IR metrics

### Documentation
- [RAG Architecture Overview](agentic-rag.md)
- [Document Ingestion Pipeline](ingestion-pipeline.md)