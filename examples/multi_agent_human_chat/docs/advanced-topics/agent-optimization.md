# Agent Optimization

Optimize agent responses using DSPy's SIMBA optimizer:

## Individual Agent Optimization

```bash
make compile-billing-optimizer     # Optimize billing agent
make compile-claims-optimizer      # Optimize claims agent
make compile-policies-optimizer    # Optimize policies agent
make compile-escalation-optimizer  # Optimize escalation agent
```

## Batch Optimization

```bash
make compile-all  # Optimize all agents sequentially
```

## Triage Classifier Optimization

```bash
make compile-triage-classifier-v2  # Few-shot classifier
make compile-triage-classifier-v4  # Zero-shot COPRO optimizer
```
