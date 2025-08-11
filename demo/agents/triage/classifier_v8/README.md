# Classifier V8 - RoBERTa with LoRA Fine-tuning

This classifier uses RoBERTa as the base model with LoRA (Low-Rank Adaptation) fine-tuning for efficient training on local GPUs.

## Key Features

- **Base Model**: RoBERTa-base (roberta-base)
- **Fine-tuning Method**: LoRA (Parameter-Efficient Fine-tuning)
- **Local GPU Support**: Optimized for CUDA training
- **Memory Efficient**: LoRA reduces trainable parameters significantly

## Configuration

The classifier can be configured via environment variables with the `TRIAGE_V8_` prefix or by modifying `config.py`.

### Key Parameters

- `TRIAGE_V8_MODEL_NAME`: Base model name (default: "roberta-base")
- `TRIAGE_V8_DEVICE`: Device for training (default: "mps" for Mac, "cuda" for NVIDIA GPUs)
- `TRIAGE_V8_TRAIN_SAMPLE_SIZE`: Number of samples for training (default: -1, use all available samples)
- `TRIAGE_V8_EVAL_SAMPLE_SIZE`: Number of samples for evaluation (default: -1, use all available samples)
- `TRIAGE_V8_LEARNING_RATE`: Learning rate (default: 2e-4)
- `TRIAGE_V8_NUM_EPOCHS`: Number of training epochs (default: 10)
- `TRIAGE_V8_BATCH_SIZE`: Training batch size (default: 8)
- `TRIAGE_V8_LORA_R`: LoRA rank (default: 16)
- `TRIAGE_V8_LORA_ALPHA`: LoRA alpha parameter (default: 32)
- `TRIAGE_V8_LORA_DROPOUT`: LoRA dropout rate (default: 0.1)

## Usage

### Training

```bash
# Set environment variables
export FINETUNE_SAMPLE_SIZE=1000
export EVALUATION_SAMPLE_SIZE=200

# Run training
python -m agents.triage.classifier_v8.finetune_trainer
```

### Inference

```python
from agents.triage.classifier_v8.classifier_v8 import classifier_v8

result = classifier_v8("User: I want to know my policy due date.")
print(f"Target Agent: {result.target_agent}")
print(f"Latency: {result.metrics.latency_ms:.2f}ms")
```

## LoRA Configuration

The LoRA configuration targets the attention layers:
- Target modules: ["query", "value"]
- Rank (r): 16
- Alpha: 32
- Dropout: 0.1

This configuration provides a good balance between performance and efficiency for sequence classification tasks.

## Model Output

The model saves to `./models/roberta-triage-v8/` by default and includes:
- LoRA adapter weights
- Tokenizer configuration
- Model configuration files

## Requirements

- PyTorch with CUDA support
- transformers
- peft
- datasets
- scikit-learn