# Triage Agent

## Overview

The Triage Agent analyzes user queries and routes them to the appropriate specialized agents in the system. It functions as the central routing intelligence, ensuring that each customer inquiry is handled by the most suitable agent based on message content.

## Key Features

- Classifies user messages using machine learning
- Routes messages to specialized agents (Billing, Claims, Policies, Escalation)
- Handles small talk directly when no specific agent is needed
- Supports multiple classifier implementations (v0-v4)
- Provides a consistent user experience through proper message routing

## Architecture

### Core Components

- **Agent Module** (`agent.py`): Core implementation that processes and routes messages
- **Config** (`config.py`): Configuration settings for the agent
- **Models** (`models.py`): Data models for message classification

### Classification System

Multiple classifier implementations with increasing sophistication:
- **v0** (`dspy_modules/classifier_v0.py`): Basic keyword-based classification
- **v1** (`dspy_modules/classifier_v1.py`): Improved prompt-based classification
- **v2** (`dspy_modules/classifier_v2/`): Optimized DSPy classifier with examples
- **v3** (`baseline_model/classifier_v3.py`): Few-shot learning baseline
- **v4** (`dspy_modules/classifier_v4/`): Advanced optimized classifier

### Triage Capabilities

The agent implements multiple DSPy-based classifiers with the Predict pattern:

- **Signature**: AgentClassificationSignature defines the business logic for message classification
- **Classification**: Uses optimized prompts to analyze message content and determine message category
- **Categories**: Routes messages to appropriate specialized agents:
  - BillingAgent: For payment and financial inquiries
  - PolicyAgent: For policy details and coverage questions
  - ClaimsAgent: For filing and checking claim status
  - EscalationAgent: For issues requiring special handling
  - ChattyAgent: Handled directly by the Triage Agent itself for greetings and general conversation

### Data Integration

Extensive datasets for training and evaluation:
- **Training Data** (`data_sets/triage-training.jsonl`): Core training examples
- **Testing Data** (`data_sets/triage-testing.jsonl`): Evaluation dataset
- **Synthetic Data Generator** (`data_sets/synthetic/`): Tools for generating additional examples

## Technical Details

### Message Classification

Messages are classified into these categories:
- **BILLING**: Payment, premium, finance-related queries
- **CLAIMS**: Filing claims, claim status, claim updates
- **POLICIES**: Coverage questions, policy details, documents
- **ESCALATION**: Complex issues needing special handling
- **SMALL_TALK**: General conversation, greetings, simple questions

### Routing Logic

Based on classification, messages are routed to:
1. **Billing Agent**: For billing-related inquiries
2. **Claims Agent**: For claim-related requests
3. **Policies Agent**: For policy and coverage questions
4. **Escalation Agent**: For complex issues requiring special handling
5. **Direct Response**: For small talk (handled within the Triage Agent)

### Evaluation Framework

The `dspy_modules/evaluation/` directory contains:
- Evaluation pipeline for classifier versions
- Performance metrics tracking
- Reporting tools for classifier benchmarking

## Development

### Training New Models

```bash
# Train a new version of the classifier
python -m agents.triage.dspy_modules.classifier_v4.classifier_v4_optimizer

# Evaluate classifier performance
python -m agents.triage.dspy_modules.evaluation.evaluate
```

### Testing

Run tests with:
```bash
make test-triage-agent
```

### Datasets

The agent includes tools for working with datasets:
- Dataset viewers for exploring training data
- Synthetic data generation tools
- Dataset transformation utilities

## Integration Points

- **Frontend Agent**: Receives all initial user messages
- **Specialized Agents**: Routes messages to appropriate specialized agents
- **Evaluation System**: Supports continuous improvement through model evaluation