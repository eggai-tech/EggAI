# Agent Capabilities Overview

## Agent Roles

| Agent | Purpose | Key Capabilities |
|-------|---------|------------------|
| **Frontend** | WebSocket gateway | Connection management, message buffering, content moderation |
| **Triage** | Intent classification & routing | ML classifiers (v0-v5), routes to specialists, handles greetings |
| **Billing** | Payment inquiries | Get/update billing info, premium amounts, payment dates |
| **Claims** | Claims management | File claims, check status, update info, estimate payouts |
| **Policies** | Document search (RAG) | Vector search, contextual answers, REST API (:8003) |
| **Escalation** | Complex issues | Multi-step workflow, ticket creation, complaint handling |
| **Audit** | Compliance logging | Monitor all channels, categorize messages, audit trail |

## Message Flow

```
User → Frontend → Triage → Specialized Agent → Response → User
                     ↓
                  Audit (logs all interactions)
```

## Agent Communication

- **Channels**: `human` (user messages), `agents` (routed requests), `audit_logs` (compliance)
- **Pattern**: Event-driven pub/sub via Redpanda
- **Scaling**: Each agent runs independently, horizontally scalable

## Running Agents

```bash
# Start all agents
make start-all

# Individual agents
make start-triage
make start-billing
# etc.
```

## Configuration

Environment variables: `{AGENT_NAME}_LANGUAGE_MODEL`, `{AGENT_NAME}_API_BASE`, etc.

---

**Previous:** [System Architecture](system-architecture.md) | **Next:** [Multi-Agent Communication](multi-agent-communication.md)