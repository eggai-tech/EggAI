# Policies Agent

## Overview

The Policies Agent provides information about insurance policy details, coverage, and terms. It uses Retrieval Augmented Generation (RAG) to retrieve accurate policy information from policy documents and answer customer questions about coverage, limits, and terms.

## Key Features

- Retrieves policy details based on policy numbers
- Answers questions about coverage, terms, and policy documents
- Uses RAG (Retrieval Augmented Generation) for accurate information
- Enforces strict privacy controls (requires policy numbers)
- References specific documentation sections for detailed answers

## Architecture

### Core Components

- **Agent Module** (`agent.py`): Main implementation that handles policy-related requests
- **Config** (`config.py`): Configuration settings for the agent
- **Types** (`types.py`): Type definitions for policies data

### RAG Implementation

The Retrieval Augmented Generation system:
- **Indexing** (`rag/indexing.py`): Creates searchable indexes of policy documents
- **Retrieving** (`rag/retrieving.py`): Retrieves relevant policy information based on queries
- **Policy Documents** (`rag/policies/`): Contains policy documents for different insurance types

### DSPy Integration

- **Policies Module** (`dspy_modules/policies.py`): DSPy models optimized for policy information
- **Optimizer** (`dspy_modules/policies_optimizer.py`): Optimizes prompts for consistent responses
- **Data Access** (`dspy_modules/policies_data.py`): Manages data operations for policy information

### Policies Capabilities

The agent implements a DSPy-based solution using the ReAct module:

- **Signature**: PolicyAgentSignature defines the business logic for handling policy interactions
- **Tools**: Provides two specialized tools for policy operations:
  - `take_policy_by_number_from_database`: Retrieves policy details using policy number
  - `query_policy_documentation`: Searches policy documentation for specific information

## Technical Details

### Policy Document Structure

The agent handles multiple policy types:
- Auto insurance (`auto.md`)
- Health insurance (`health.md`)
- Home insurance (`home.md`)
- Life insurance (`life.md`)

### Data Privacy

The agent implements strict privacy controls:
- Requires valid policy numbers before disclosing information
- Validates user identity based on matching information
- Protects sensitive policy details using appropriate access controls

### RAG Pipeline

1. User query is analyzed for intent
2. Policy documents are retrieved based on policy number and query
3. Relevant sections are extracted and ranked
4. DSPy generates a response using the retrieved context
5. Response includes specific references to policy sections

## Development

### Testing

Test the Policies Agent with:
```bash
make test-policies-agent
```

### Extending

To add support for new policy types:
1. Add policy documents to `rag/policies/`
2. Update the indexing system if needed
3. Add handling for the new policy type in `agent.py`
4. Update DSPy models to handle the new policy type
5. Add test cases for the new policy type

## Integration Points

- **Frontend Agent**: Provides the user interface for policy inquiries
- **Triage Agent**: Routes policy-related questions to this agent
- **Billing Agent**: May cross-reference with policy information
- **Claims Agent**: May need policy details for claims processing