# Billing Agent

The Billing Agent handles all payment and financial inquiries for insurance policies.

- **Purpose**: Handles financial and payment inquiries
- **Key Features**:
  - Retrieves billing information by policy number
  - Provides premium amounts and due dates
  - Updates payment information
  - Privacy controls (requires policy number)
- **Tools**: `get_billing_info`, `update_billing_info`

## Quick Start

```bash
# From the project root
make start-billing

# Or run directly
python -m agents.billing.main
```

### Configuration

Key environment variables:

```bash
BILLING_LANGUAGE_MODEL=lm_studio/gemma-3-12b-it  # Or openai/gpt-4o-mini
BILLING_PROMETHEUS_METRICS_PORT=9092
```

## Tools

The agent uses ReAct pattern with these tools:

1. **get_billing_info(policy_number: str)**
   - Retrieves billing details for a specific policy
   - Returns premium amount, due date, and payment status

2. **update_billing_info(policy_number: str, field: str, value: str)**
   - Updates billing information fields
   - Supports payment method changes

## Example Interactions

```
User: "What's my premium for policy B67890?"
Agent: Retrieves billing info and provides premium details

User: "When is my next payment due?"
Agent: Checks policy number first, then provides due date
```

## Development

### Testing

```bash
# Run all billing tests
make test-billing-agent

# Run specific test files
pytest agents/billing/tests/test_agent.py -v
```

### Running with Custom Settings

```bash
BILLING_LANGUAGE_MODEL=openai/gpt-4o-mini \
OPENAI_API_KEY=your-key \
make start-billing
```

### Optimization

Optimize the agent's responses:

```bash
make compile-billing-optimizer
```

## Architecture

- **Channel**: Listens on `agents` channel for `billing_request` messages
- **Output**: Publishes to `human` channel
- **Streaming**: Supports real-time response streaming
- **Tracing**: Full OpenTelemetry support for debugging

## Monitoring

- Prometheus metrics: http://localhost:9092/metrics
- Grafana dashboards: http://localhost:3000
- MLflow tracking: http://localhost:5001