# Escalation Agent

Handles complex issues, complaints, and requests requiring special attention.

## What it does
- Creates support tickets for complex issues
- Routes to appropriate departments
- Tracks ticket status and updates
- Handles complaints professionally

## Quick Start
```bash
make start-escalation
```

## Configuration
```bash
ESCALATION_LANGUAGE_MODEL=lm_studio/gemma-3-12b-it  # Or openai/gpt-4o-mini
```

## Tools
- `create_ticket(description, department, priority)` - Creates support ticket
- `get_ticket_status(ticket_id)` - Returns current status
- `update_ticket(ticket_id, update)` - Adds notes to ticket

Departments: Technical Support, Billing, Sales

## Testing
```bash
make test-escalation-agent
```