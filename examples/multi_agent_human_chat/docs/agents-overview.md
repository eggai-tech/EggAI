# Agent Capabilities Overview

## Agent Roles

| Agent | Purpose | Key Capabilities |
|-------|---------|------------------|
| **Frontend** | Web UI & WebSocket gateway | Serves chat interface, manages connections, buffers messages |
| **Triage** | Request routing | Classifies intent (ML), routes to specialists, handles greetings |
| **Billing** | Payment & premiums | Retrieves/updates billing info, payment dates, amounts |
| **Claims** | Claims processing | Files new claims, checks status, updates info, estimates |
| **Policies** | Coverage & documents | Personal policy data, RAG document search, coverage Q&A |
| **Escalation** | Complex issues | Multi-step workflows, support tickets, complaints |
| **Audit** | Compliance tracking | Logs all messages, categorizes by domain, audit trail |

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