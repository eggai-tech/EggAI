# Claims Agent

The Claims Agent manages insurance claim inquiries, status checks, and new claim filing.

- **Purpose**: Manages insurance claims inquiries
- **Key Features**:
  - Retrieves claim status
  - Files new claims
  - Updates existing claims
  - Provides estimated payouts
- **Tools**: `get_claim_status`, `create_claim`, `update_claim`

## Quick Start

```bash
# From the project root
make start-claims

# Or run directly
python -m agents.claims.main
```

### Configuration

Key environment variables:

```bash
CLAIMS_LANGUAGE_MODEL=lm_studio/gemma-3-12b-it  # Or openai/gpt-4o-mini
CLAIMS_PROMETHEUS_METRICS_PORT=9093
```

## Tools

The agent uses ReAct pattern with these tools:

1. **get_claim_status(claim_number: str)**
   - Retrieves current status of a claim
   - Returns status, last update, and next steps

2. **file_new_claim(policy_number: str, incident_details: str)**
   - Initiates a new claim
   - Returns claim number and initial status

3. **get_claim_history(policy_number: str)**
   - Lists all claims for a policy
   - Includes dates and statuses

## Example Interactions

> **User**: _"I want to file a claim for my car accident"_  
> **Agent**: Asks for policy number and incident details, then files claim
>
> **User**: _"What's the status of claim CL789012?"_  
> **Agent**: Retrieves and provides current claim status

## Development

### Testing

```bash
# Run all claims tests
make test-claims-agent

# Run specific test files
pytest agents/claims/tests/test_agent.py -v
```

### Running with Custom Settings

```bash
CLAIMS_LANGUAGE_MODEL=openai/gpt-4o-mini \
OPENAI_API_KEY=your-key \
make start-claims
```

### Optimization

Optimize the agent's responses:

```bash
make compile-claims-optimizer
```

## Architecture

- **Channel**: Listens on `agents` channel for `claim_request` messages
- **Output**: Publishes to `human` channel
- **Streaming**: Supports real-time response streaming
- **Tracing**: Full OpenTelemetry support for debugging

## Monitoring

- Prometheus metrics: http://localhost:9093/metrics
- Grafana dashboards: http://localhost:3000
- MLflow tracking: http://localhost:5001