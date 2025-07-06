# Triage Agent

The Triage Agent analyzes incoming messages and routes them to the appropriate specialized agent using ML-based classification.

## Quick Start

```bash
# From the project root
make start-triage

# Or run directly
python -m agents.triage.main
```

## Features

- ML-powered message classification
- Routes to: Billing, Claims, Policies, or Escalation agents
- Handles small talk directly
- Multiple classifier versions (v0-v5)
- Real-time streaming responses

## Configuration

Key environment variables:
```bash
TRIAGE_LANGUAGE_MODEL=lm_studio/gemma-3-12b-it  # Or openai/gpt-4o-mini
TRIAGE_PROMETHEUS_METRICS_PORT=9091
TRIAGE_CLASSIFIER_VERSION=v4  # Choose classifier version (v0-v5)
```

## Classifier Versions

1. **v0**: Basic prompt-based classification
2. **v1**: Enhanced prompt with examples
3. **v2**: DSPy optimized few-shot
4. **v3**: Baseline few-shot with training
5. **v4**: Zero-shot COPRO optimized (default)
6. **v5**: Attention-based neural classifier

## Testing

```bash
# Run all triage tests
make test-triage-agent

# Test specific classifier version
make test-triage-classifier-v4

# Run comprehensive evaluation
pytest agents/triage/tests/test_agent.py::test_triage_agent -v
```

## Training Classifiers

```bash
# Train baseline classifier
make train-triage-classifier-v3

# Train attention-based classifier
make train-triage-classifier-v5

# Optimize DSPy classifiers
make compile-triage-classifier-v2
make compile-triage-classifier-v4
```

## Routing Logic

The agent routes messages based on content:

- **Billing**: Payment questions, premiums, invoices
- **Claims**: Claim status, filing new claims, incidents
- **Policies**: Coverage questions, policy terms, documents
- **Escalation**: Complaints, complex issues, frustration
- **Small Talk**: Greetings, general chat (handled directly)

## Example Interactions

```
User: "Hi, how are you?"
Triage: Handles directly with friendly response

User: "What's my premium for policy B12345?"
Triage: Routes to Billing Agent

User: "I want to file a claim"
Triage: Routes to Claims Agent
```

## Development

### Running with Custom Classifier

```bash
TRIAGE_CLASSIFIER_VERSION=v5 \
TRIAGE_LANGUAGE_MODEL=openai/gpt-4o-mini \
make start-triage
```

### Evaluating Performance

View classifier performance metrics:
- MLflow UI: http://localhost:5001
- Check precision, recall, and F1 scores
- Compare different classifier versions

## Architecture

- **Input Channel**: Listens on `agents` channel for `user_message`
- **Output Channels**: Routes to specialized agents via `agents` channel
- **Small Talk**: Publishes directly to `human_stream` channel
- **Classification**: Configurable ML classifiers
- **Metrics**: Tracks routing accuracy and latency

## Monitoring

- Prometheus metrics: http://localhost:9091/metrics
- Grafana dashboards: http://localhost:3000
- MLflow experiments: http://localhost:5001
- Classification reports in `agents/triage/tests/reports/`