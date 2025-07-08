# EggAI Message Protocol

## Message Flow Overview

**Frontend Agent:**
- Receives: user input via WebSocket
- Publishes: UserMessage → human channel

**Triage Agent:**
- Subscribes to: UserMessage (human channel)
- Publishes: BillingRequestMessage | ClaimRequestMessage | PolicyRequestMessage | EscalationRequestMessage → agents channel

**Billing/Claims/Policies/Escalation Agents:**
- Subscribe to: *RequestMessage (agents channel)
- Publish: AgentMessage, StreamChunkMessage, StreamEndMessage → human/human_stream channels

**Audit Agent:**
- Subscribes to: all messages (agents + human channels)
- Publishes: AuditLogMessage → audit_logs channel

## Message Payload Examples

### UserMessage
```json
{
  "id": "uuid",
  "type": "user_message",
  "source": "Frontend",
  "data": {
    "connection_id": "websocket-123",
    "chat_messages": [
      {"role": "user", "content": "What's my premium?"}
    ]
  }
}
```

### BillingRequestMessage
```json
{
  "id": "uuid", 
  "type": "billing_request",
  "source": "Triage",
  "data": {
    "connection_id": "websocket-123",
    "chat_messages": [
      {"role": "user", "content": "What's my premium?"},
      {"role": "assistant", "content": "I'll help you check your premium."}
    ]
  }
}
```

### AgentMessage
```json
{
  "id": "uuid",
  "type": "agent_message",
  "source": "Billing",
  "data": {
    "connection_id": "websocket-123",
    "message": "Your current premium is $150/month.",
    "agent": "Billing"
  }
}
```

## Protocol Structure

- **enums.py** - Message types, agent names, and other constants
- **messages.py** - TypedDict definitions for all message types and type guards
- **__init__.py** - Exports all protocol definitions

## Usage

```python
from libraries.protocol import MessageType, AgentName, BillingRequestMessage

# Type checking
if msg.type == MessageType.BILLING_REQUEST:
    # Handle billing request
```