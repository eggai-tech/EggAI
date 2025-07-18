# Agent Performance Optimization

This guide covers optimization techniques for both DSPy-based agents and the Triage classifier.

## DSPy Agent Optimization

### SIMBA Optimizer

SIMBA (Simple Instruction Following via Bootstrapping) optimizes agent prompts automatically:

```bash
make compile-billing-optimizer     # Optimize billing agent
make compile-claims-optimizer      # Optimize claims agent
make compile-policies-optimizer    # Optimize policies agent
make compile-escalation-optimizer  # Optimize escalation agent
```

### Batch Optimization

```bash
make compile-all  # Optimize all agents sequentially
```

## Triage Classifier Optimization

The Triage agent evolved through multiple versions, from basic prompts to advanced neural networks:

### Classifier Evolution

| Version | Type | Optimization Method |
|---------|------|---------------------|
| **v0** | Basic prompt | None (baseline) |
| **v1** | Enhanced prompt | Manual examples |
| **v2** | DSPy few-shot | Auto-optimized with examples |
| **v3** | ML baseline | Logistic regression training |
| **v4** | DSPy zero-shot | COPRO optimization (recommended) |
| **v5** | Neural network | Attention-based training |

### 1. Unoptimized Baselines (v0, v1)

Test the unoptimized versions to establish baseline performance:

```bash
# Test basic prompt classifier
make test-triage-classifier-v0

# Test enhanced prompt with examples
make test-triage-classifier-v1
```

### 2. DSPy-Based Optimizers (v2, v4)

```bash
# Compile and test few-shot classifier
make compile-triage-classifier-v2
make test-triage-classifier-v2

# Compile and test zero-shot COPRO optimizer (recommended)
make compile-triage-classifier-v4
make test-triage-classifier-v4
```

**COPRO** (Compositional Preference Optimization) automatically discovers optimal prompts without training data.

### 3. Custom ML Classifiers (v3, v5)

For improved latency and cost reduction:

```bash
# Train custom classifiers
make train-triage-classifier-v3  # Logistic regression (100 examples/class)
make train-triage-classifier-v5  # Attention-based neural network

# Test performance
make test-triage-classifier-v3
make test-triage-classifier-v5
```

### 4. Performance Comparison

Run comprehensive comparison across all versions:

```bash
# Run all classifier tests to compare in MLflow
for v in 0 1 2 3 4 5; do
    make test-triage-classifier-v$v
done

# View results in MLflow UI
# http://localhost:5001
```

### 5. Performance Monitoring

View metrics and comparisons in MLflow:
- **URL**: http://localhost:5001
- **Experiments**: Organized by classifier version
- **Metrics**: Accuracy, F1 score, latency (mean/p95/max), token usage
- **Reports**: HTML reports in `agents/triage/tests/reports/`

#### Key Metrics to Compare:
- **Accuracy**: Classification correctness
- **Latency**: Response time (critical for user experience)
- **Token Usage**: Cost implications (prompt + completion tokens)
- **Consistency**: Performance variance across test runs

## Optimization Journey: From Basic to Advanced

### The Evolution Story

1. **v0 → v1**: Added manual examples to improve consistency
2. **v1 → v2**: Automated optimization with DSPy few-shot learning
3. **v2 → v4**: Eliminated need for examples with zero-shot COPRO
4. **Parallel Track**: v3 (traditional ML) and v5 (neural) for production efficiency

### Optimization Strategies

#### When to Use Each Approach:

1. **SIMBA (Individual Agents)**: Best for optimizing ReAct agents with complex tool usage
2. **COPRO (Triage v4)**: Zero-shot prompt optimization when you lack training data
3. **Few-Shot (Triage v2)**: When you have limited examples but want DSPy flexibility
4. **Custom ML (v3/v5)**: Production deployments requiring low latency and cost

#### Trade-offs:

| Approach | Pros | Cons |
|----------|------|------|
| **Unoptimized (v0/v1)** | Simple, no setup | Lower accuracy, inconsistent |
| **DSPy Optimized (v2/v4)** | Auto-optimization, flexible | Requires compilation step |
| **Custom ML (v3/v5)** | Fast inference, low cost | Requires training data, less flexible |


---

**Previous:** [Vespa Search Guide](../vespa-search-guide.md) | **Next:** [Deployment Guide](multi-environment-deployment.md)
