# Retrieval Performance Testing

This directory contains a comprehensive test suite for evaluating the quality of document retrieval systems using context-based similarity metrics and LLM judges.

## Overview

The test suite evaluates retrieval performance using real QA pairs from insurance policy documents. Instead of relying on predefined chunk IDs, it uses **context similarity** to measure how well retrieved chunks match the expected content.

## Architecture

The test suite consists of three main stages:

1. **Stage 1: Query Execution** - Performs retrieval queries with different parameters
2. **Stage 2: LLM Evaluation** - Uses GPT-4o-mini to evaluate retrieval quality
3. **Stage 3: MLflow Reporting** - Logs comprehensive metrics and results

## Key Files

- `filtered_qa_pairs.json` - Test dataset with questions, answers, and expected context
- `evaluator.py` - Core evaluation logic with context similarity and ranking metrics
- `models.py` - Data models for test cases and results
- `test_data.py` - Test data loading and management
- `mlflow_reporter.py` - MLflow integration for metrics tracking
- `api_client.py` - API client for retrieval system integration

## Evaluation Metrics

### Context-Based Metrics

#### Recall/Hit Rate
- **Purpose**: Measures whether relevant context was found in retrieved chunks
- **Calculation**: Binary score (1.0 if any chunk similarity ≥ threshold, 0.0 otherwise)
- **Interpretation**: Higher is better (0.0 - 1.0)
- **Use Case**: Answers "Did we find the relevant information?"

#### Context Coverage
- **Purpose**: Measures how much of the expected context is covered by the best matching chunk
- **Calculation**: Maximum similarity score across all retrieved chunks using SequenceMatcher
- **Interpretation**: Higher is better (0.0 - 1.0)
- **Use Case**: Answers "How complete is our best match?"

### Ranking Metrics

#### Precision@k
- **Purpose**: Measures the precision of top-k retrieved results
- **Calculation**: (Number of relevant chunks in top-k) / k
- **Parameters**: Default k=5, relevance threshold=0.5
- **Interpretation**: Higher is better (0.0 - 1.0)
- **Use Case**: Answers "How many of our top results are actually relevant?"

#### Mean Reciprocal Rank (MRR)
- **Purpose**: Measures the ranking quality with emphasis on early results
- **Calculation**: 1 / (position of first relevant result)
- **Interpretation**: Higher is better (0.0 - 1.0)
- **Use Case**: Answers "How high up was our first good result?"

#### Normalized Discounted Cumulative Gain (nDCG)
- **Purpose**: Sophisticated ranking metric that considers both relevance and position
- **Calculation**: DCG / IDCG with logarithmic position discounting
- **Parameters**: Default k=10
- **Interpretation**: Higher is better (0.0 - 1.0)
- **Use Case**: Answers "How good is our overall ranking quality?"

#### Best Match Position
- **Purpose**: Tracks the position (1-indexed) of the best matching chunk
- **Calculation**: Position of chunk with highest similarity score ≥ threshold
- **Interpretation**: Lower is better (1 = best)
- **Use Case**: Answers "Where did our best result appear in the ranking?"

### Position-Based Hit Rates

- **Hit Rate @ Top-1**: Percentage of queries where relevant content appears in position 1
- **Hit Rate @ Top-3**: Percentage of queries where relevant content appears in positions 1-3
- **Hit Rate @ Top-5**: Percentage of queries where relevant content appears in positions 1-5

### LLM Judge Metrics

#### Retrieval Quality Score
- **Purpose**: Overall quality assessment by LLM judge
- **Scale**: 0.0 - 1.0 (0.9-1.0=Excellent, 0.7-0.8=Good, 0.5-0.6=Adequate, 0.3-0.4=Poor, 0.0-0.2=Inadequate)
- **Threshold**: ≥0.7 for pass judgment

#### Completeness Score
- **Purpose**: How complete the retrieved information is for answering the question
- **Scale**: 0.0 - 1.0

#### Relevance Score
- **Purpose**: How relevant the retrieved chunks are to the question
- **Scale**: 0.0 - 1.0

## Configuration

### Evaluation Modes

#### LLM Judge Enabled (Default)
```python
config = RetrievalTestConfiguration(enable_llm_judge=True)
evaluator = RetrievalEvaluator(enable_llm_judge=True)
```
- Uses GPT-4o-mini for quality assessment
- Provides detailed reasoning and insights
- Requires OpenAI API key
- Higher evaluation cost and latency

#### LLM Judge Disabled (Context-Only)
```python
config = RetrievalTestConfiguration(enable_llm_judge=False)
evaluator = RetrievalEvaluator(enable_llm_judge=False)
```
- Uses only context similarity metrics
- Faster evaluation with lower cost
- No external API dependencies
- LLM-specific metrics set to 0.0:
  - `retrieval_quality_score` = 0.0 (not evaluated)
  - `completeness_score` = 0.0 (not evaluated)
  - `relevance_score` = 0.0 (not evaluated)
  - `judgment` = False (not evaluated)
- Focus on context-based metrics: `recall_score`, `precision_at_k`, `mrr_score`, `ndcg_score`, `context_coverage`

### Search Types
- `hybrid` - Combines keyword and vector search
- `keyword` - Traditional keyword-based search
- `vector` - Semantic vector search

### Max Hits Values
- `1` - Retrieve only the top result
- `5` - Retrieve top 5 results
- `10` - Retrieve top 10 results

### Similarity Thresholds
- **Default threshold**: 0.5 for determining relevance
- **Adjustable**: Can be modified in evaluator methods

## Usage

### Running Tests

#### With LLM Judge (Default)
```python
from agents.policies.tests.retrieval_performance.test_data import get_retrieval_test_cases
from agents.policies.tests.retrieval_performance.evaluator import RetrievalEvaluator
from agents.policies.tests.retrieval_performance.models import RetrievalTestConfiguration

# Configure with LLM judge enabled
config = RetrievalTestConfiguration(enable_llm_judge=True)
test_cases = get_retrieval_test_cases()
evaluator = RetrievalEvaluator(enable_llm_judge=True)
```

#### Context-Only Mode (No LLM)
```python
# Configure with LLM judge disabled
config = RetrievalTestConfiguration(enable_llm_judge=False)
test_cases = get_retrieval_test_cases()
evaluator = RetrievalEvaluator(enable_llm_judge=False)
```

### Viewing Results

Results are automatically logged to MLflow with the experiment name `retrieval_performance_evaluation`. Key metrics to monitor:

- `avg_recall_score` - Overall hit rate
- `avg_context_coverage` - Average content coverage
- `avg_mrr_score` - Average ranking quality
- `hit_rate_top_1` - Percentage of queries with relevant result in top position

## Test Data

The test dataset is loaded from `filtered_qa_pairs.json`, which contains:

- **Questions**: Real user questions about insurance policies
- **Answers**: Expected correct answers
- **Context**: The actual text content that should be retrieved
- **Source**: Origin document and metadata

Example test case structure:
```json
{
  "question": "What is the purpose of the Accidental Death Benefit Rider?",
  "answer": "The Accidental Death Benefit Rider enhances the base death benefit...",
  "context": "At the discretion of the Insured and subject to the payment of...",
  "source_document": "life.md",
  "qa_pair_id": "QA_2"
}
```

## Interpreting Results

### Good Performance Indicators
- **Recall Score**: > 0.8 (80% of queries find relevant content)
- **Context Coverage**: > 0.6 (60% content similarity on average)
- **MRR Score**: > 0.7 (relevant results typically in top 3)
- **Hit Rate @ Top-1**: > 0.5 (50% of queries have best result first)

### Poor Performance Indicators
- **Low Recall**: < 0.5 (missing relevant content)
- **Low Context Coverage**: < 0.3 (poor content matching)
- **Low MRR**: < 0.3 (relevant results buried deep)
- **Low Hit Rate @ Top-1**: < 0.2 (poor ranking quality)

## Troubleshooting

### Common Issues

1. **Low Context Coverage**: Check if chunk sizes are appropriate for the expected context length
2. **High Recall but Low MRR**: Relevant content is found but poorly ranked
3. **Zero Scores**: Check API connectivity and chunk text extraction
4. **Inconsistent Results**: Verify test data quality and similarity threshold settings