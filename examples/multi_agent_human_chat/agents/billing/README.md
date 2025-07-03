# Billing Agent

## Overview

The Billing Agent handles financial and payment-related inquiries for insurance customers. It provides information about premium amounts, payment due dates, payment status, and processes payment updates.

## Key Features

- Retrieves billing information using policy numbers
- Processes inquiries about premium amounts and due dates
- Handles payment status inquiries 
- Updates billing records and payment information
- Enforces privacy controls requiring policy numbers for financial information

## Architecture

### Core Components

- **Agent Module** (`agent.py`): Main implementation that handles incoming billing requests
- **Config** (`config.py`): Configuration settings for the agent
- **DSPy Integration**: 
  - Utilizes optimized DSPy models for consistent response generation
  - Pre-trained prompts ensure accurate and relevant billing information

### Message Flow

1. Messages are received through the agents channel
2. Policy information is validated
3. Billing queries are processed using DSPy models
4. Responses are published back through the human channel

## Technical Details

### Message Handling

The agent subscribes to the `agents` channel and filters for `billing_request` message types. It requires a valid policy number before disclosing any financial information, maintaining data privacy.

```python
@billing_agent.subscribe(
    channel=agents_channel, 
    filter_by_message=lambda msg: msg.get("type") == "billing_request"
)
```

### DSPy Integration

The agent leverages DSPy for natural language understanding and generation:

  - `libraries/billing_dspy/billing.py`: Main DSPy models for processing billing queries
  - `libraries/billing_dspy/billing_optimizer.py`: Optimization for consistent responses
  - `libraries/billing_dspy/billing_data.py`: Data operations for billing information

### Billing Capabilities

The agent implements a DSPy-based solution using the ReAct module:

- **Signature**: BillingSignature defines the business logic for handling billing interactions
- **Tools**: Provides two specialized tools for billing operations:
  - `get_billing_info`: Retrieves billing information for policies
  - `update_billing_info`: Updates payment information and billing records

### OpenTelemetry Integration

The agent uses OpenTelemetry for comprehensive tracing and monitoring:

- Spans for each request processing stage
- Attribute tracking for performance metrics
- Error tracking for failed billing operations

## Development

### Testing

Test your changes with:

```bash
make test-billing-agent
```

### Extending

To add new billing capabilities:

1. Update the DSPy modules in `libraries/billing_dspy/`
2. Add handling for new message types in `agent.py`
3. Add test cases in `tests/test_agent.py`

## Integration Points

- **Frontend Agent**: Receives user messages and sends responses
- **Triage Agent**: Routes appropriate billing inquiries to this agent
- **Policies Agent**: May cross-reference for policy verification