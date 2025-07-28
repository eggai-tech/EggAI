# Classifier V6 - OpenAI Fine-tuned

Fine-tuned GPT-4o-mini for triage classification using OpenAI's fine-tuning API.

## Benefits

**Performance**
- Higher accuracy on domain-specific triage decisions
- More consistent classification behavior
- Specialized knowledge of agent roles and routing

**Efficiency** 
- Shorter prompts (knowledge stored in model weights)
- Reduced token usage per classification
- Faster inference without complex instructions

**Production**
- No prompt engineering required
- Reliable behavior at scale
- Less maintenance overhead

## Setup

```bash
make train-triage-classifier-v6
export TRIAGE_CLASSIFIER_VERSION="v6"
```

## Usage

```python
from agents.triage.classifier_v6.classifier_v6 import classifier_v6

result = classifier_v6(chat_history="User: I need help with my claim")
```

## Training Options

```bash
# Demo (20 examples)
make train-triage-classifier-v6

# Custom size
FINETUNE_SAMPLE_SIZE=100 make train-triage-classifier-v6

# Full dataset
FINETUNE_SAMPLE_SIZE=-1 make train-triage-classifier-v6
```

## Testing

```bash
make test-triage-classifier-v6
```