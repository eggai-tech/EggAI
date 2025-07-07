# Escalation Agent

The Escalation Agent handles complex issues, complaints, and requests that require special attention or human intervention.

- **Purpose**: Handles complex issues requiring human attention
- **Key Features**:
  - Multi-step escalation workflow
  - State-based conversation management
  - Support ticket creation
  - Handles complaints and technical issues
- **Workflow**: Reason → Details → Confirmation → Ticket Creation

## Quick Start

```bash
# From the project root
make start-escalation

# Or run directly
python -m agents.escalation.main
```

## Features

- Create support tickets for complex issues
- Route to appropriate departments
- Track ticket status and updates
- Handle customer complaints professionally

## Configuration

Key environment variables:

```bash
ESCALATION_LANGUAGE_MODEL=lm_studio/gemma-3-12b-it  # Or openai/gpt-4o-mini
ESCALATION_PROMETHEUS_METRICS_PORT=9094
ESCALATION_TICKET_DATABASE_PATH=./tickets.db  # SQLite database location
```

## Testing

```bash
# Run all escalation tests
make test-escalation-agent

# Run specific test files
pytest agents/escalation/tests/test_agent.py -v
```

## Tools

The agent uses ReAct pattern with these tools:

1. **create_ticket(description: str, department: str, priority: str)**
   - Creates a new support ticket
   - Returns ticket ID for tracking
   - Departments: Technical Support, Billing, Sales

2. **get_ticket_status(ticket_id: str)**
   - Retrieves current ticket status
   - Shows last update and assigned department

3. **update_ticket(ticket_id: str, update: str)**
   - Adds notes or updates to existing ticket
   - Maintains audit trail

## Example Interactions

```
User: "I've been trying to resolve this for weeks and I'm frustrated!"
Agent: Creates high-priority ticket and provides ticket number

User: "What's the status of ticket TK-12345?"
Agent: Retrieves and provides current ticket status and updates
```

## Development

### Running with Custom Settings

```bash
ESCALATION_LANGUAGE_MODEL=openai/gpt-4o-mini \
OPENAI_API_KEY=your-key \
make start-escalation
```

### Database Management

The agent uses SQLite for ticket storage:

```python
# Database schema
CREATE TABLE tickets (
    ticket_id TEXT PRIMARY KEY,
    description TEXT,
    department TEXT,
    priority TEXT,
    status TEXT,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);
```

### Optimization

Optimize the agent's responses:

```bash
make compile-escalation-optimizer
```

## Architecture

- **Channel**: Listens on `agents` channel for `ticketing_request` messages
- **Output**: Publishes to `human` channel
- **Storage**: SQLite database for ticket persistence
- **Streaming**: Supports real-time response streaming
- **Tracing**: Full OpenTelemetry support for debugging

## Monitoring

- Prometheus metrics: http://localhost:9094/metrics
- Grafana dashboards: http://localhost:3000
- MLflow tracking: http://localhost:5001