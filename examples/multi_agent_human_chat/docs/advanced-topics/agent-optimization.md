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

The Triage agent supports multiple optimization approaches:

### 1. DSPy-Based Optimizers

```bash
make compile-triage-classifier-v2  # Few-shot classifier with examples
make compile-triage-classifier-v4  # Zero-shot COPRO optimizer
```

**COPRO** (Compositional Preference Optimization) automatically discovers optimal prompts without training data.

### 2. Custom ML Classifiers

For improved latency and cost reduction:

```bash
# Train custom classifiers
make train-triage-classifier-v3  # Logistic regression (100 examples/class)
make train-triage-classifier-v5  # Attention-based neural network

# Test performance
make test-triage-classifier-v3
make test-triage-classifier-v5
```

### 3. Performance Monitoring

View training metrics and model comparisons:
- MLflow UI: http://localhost:5001
- Experiments organized by model version
- Track accuracy, F1 score, and latency

## Optimization Strategies

### When to Use Each Approach:

1. **SIMBA (Individual Agents)**: Best for optimizing ReAct agents with complex tool usage
2. **COPRO (Triage v4)**: Zero-shot prompt optimization when you lack training data
3. **Few-Shot (Triage v2)**: When you have limited examples but want DSPy flexibility
4. **Custom ML (v3/v5)**: Production deployments requiring low latency and cost


---

**Previous:** [Vespa Search Guide](../vespa-search-guide.md) | **Next:** [Deployment Guide](multi-environment-deployment.md)
