# Audit Agent

## Overview

The Audit Agent monitors and logs all message activity across the platform, creating a central audit trail for compliance, debugging, and analytics purposes.

## Functionality

- **Message Capturing**: Subscribes to both `human` and `agents` channels to intercept all messages
- **Categorization**: Classifies messages into domains (User Communication, Billing, Policies, etc.)
- **Audit Log Generation**: Creates standardized audit records with consistent metadata
- **Error Handling**: Gracefully handles malformed messages and processing exceptions

## Audit Capabilities

The agent monitors system communication and generates audit logs:

- **Monitoring**: Subscribes to all `human` and `agents` channel messages
- **Logging**: Publishes standardized audit records to the `audit_logs` channel

## Process Flow

1. Message arrives on `human` or `agents` channel
2. Audit agent extracts message metadata (ID, type, source)
3. Message is categorized based on its type
4. Standardized audit log is created and published to `audit_logs` channel
5. Telemetry spans capture performance data

## Message Categories

```python
MESSAGE_CATEGORIES = {
    "agent_message": "User Communication",
    "billing_request": "Billing",
    "policy_request": "Policies", 
    "escalation_request": "Escalation",
    "triage_request": "Triage",
}
```

## Audit Log Format

```json
{
  "type": "audit_log",
  "source": "AuditAgent",
  "data": {
    "message_id": "9a310b9a-1af5-4a8c-9cf9-c6b0c1a8580e",
    "message_type": "policy_request",
    "message_source": "FrontendAgent",
    "channel": "agents",
    "category": "Policies",
    "audit_timestamp": "2025-05-11T08:15:23.456789"
  }
}
```

## Testing

Integration tests verify:
- Basic messaging functionality
- All message type categorization
- Error handling for edge cases