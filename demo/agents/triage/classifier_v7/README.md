# Classifier V7 - Gemma3 Fine-tuned

Local Gemma3 fine-tuning for triage classification using HuggingFace Transformers + LoRA.

## Features

- **Local inference** - No API costs, data stays private
- **LoRA fine-tuning** - Efficient training with ~1.3% trainable parameters  
- **Mac GPU support** - Uses Metal Performance Shaders (MPS)
- **QAT models** - Support for Quantized Aware Training variants
- **MLflow tracking** - Model versioning and experiment logging

## Quick Start

```bash
# Train with default settings (20 examples, Gemma 3-1b)
make train-triage-classifier-v7

# Use the trained model
export TRIAGE_CLASSIFIER_VERSION="v7"
```

## Usage

```python
from agents.triage.classifier_v7.classifier_v7 import classifier_v7

result = classifier_v7(chat_history="User: I need help with my claim")
print(result.target_agent)  # e.g., "ClaimsAgent"
```

## Configuration

```bash
# More training examples
FINETUNE_SAMPLE_SIZE=100 make train-triage-classifier-v7

# Different Gemma model
TRIAGE_V7_MODEL_NAME=google/gemma-3-2b-it make train-triage-classifier-v7

# Use QAT model (better quantization)
TRIAGE_V7_USE_QAT_MODEL=true make train-triage-classifier-v7

# Test the trained model
make test-triage-classifier-v7
```

**Defaults**: Gemma 3-1b, LoRA rank 16, 20 training examples