# EggAI Agents Overview

This document provides a comprehensive overview of all agents in the EggAI system.

## System Architecture

The EggAI system consists of specialized agents that work together to handle insurance-related customer inquiries:

|   | Agent       | Description                                      | Documentation                              |
|---|-------------|--------------------------------------------------|---------------------------------------------|
| ![Frontend Agent](https://raw.githubusercontent.com/eggai-tech/EggAI/refs/heads/main/docs/docs/assets/avatar/frontend-agent.png) | Frontend    | Gateway for user interaction           | [Frontend Agent Docs](../agents/frontend/README.md)     |
| ![Triage Agent](https://raw.githubusercontent.com/eggai-tech/EggAI/refs/heads/main/docs/docs/assets/avatar/triage-agent.png) | Triage      | ML-based routing to appropriate agents           | [Triage Agent Docs](../agents/triage/README.md)         |
| ![Billing Agent](https://raw.githubusercontent.com/eggai-tech/EggAI/refs/heads/main/docs/docs/assets/avatar/billing-agent.png) | Billing     | Payment inquiries and premium information        | [Billing Agent Docs](../agents/billing/README.md)       |
| ![Claims Agent](https://raw.githubusercontent.com/eggai-tech/EggAI/refs/heads/main/docs/docs/assets/avatar/claims-agent.png) | Claims      | Claims status and filing                         | [Claims Agent Docs](../agents/claims/README.md)         |
| ![Policies Agent](https://raw.githubusercontent.com/eggai-tech/EggAI/refs/heads/main/docs/docs/assets/avatar/policies-agent.png) | Policies    | RAG-powered policy document search               | [Policies Agent Docs](../agents/policies/README.md)     |
| ![Escalation Agent](https://raw.githubusercontent.com/eggai-tech/EggAI/refs/heads/main/docs/docs/assets/avatar/escalation-agent.png) | Escalation  | Complex issues and complaints                    | [Escalation Agent Docs](../agents/escalation/README.md) |
| ![Ausdit Agent](https://raw.githubusercontent.com/eggai-tech/EggAI/refs/heads/main/docs/docs/assets/avatar/audit-agent.png) | Audit       | Compliance logging                               | [Audit Agent Docs](../agents/audit/README.md)           |


## Agent Details

### Frontend Agent
<img src="https://raw.githubusercontent.com/eggai-tech/EggAI/refs/heads/main/docs/docs/assets/avatar/frontend-agent.png" width="40"/>

- **Purpose**: Manages WebSocket connections between users and backend
- **Key Features**: 
  - Real-time bidirectional communication
  - Connection state management
  - Message buffering for offline connections
  - Optional content moderation via Guardrails
- **Channels**: Listens on `human`, publishes to `agents`

**See: [Frontend Agent Documentation](../agents/frontend/README.md)**

### Triage Agent
<img src="https://raw.githubusercontent.com/eggai-tech/EggAI/refs/heads/main/docs/docs/assets/avatar/triage-agent.png" width="40"/>

- **Purpose**: Analyzes and routes user messages to appropriate agents
- **Key Features**:
  - ML-based message classification (v0-v4 classifiers)
  - Routes to: Billing, Claims, Policies, or Escalation
  - Handles small talk directly
  - Supports multiple classifier implementations
- **Channels**: Listens on `agents`, publishes routing decisions

**See: [Triage Agent Documentation](../agents/triage/README.md)**

### Billing Agent
<img src="https://raw.githubusercontent.com/eggai-tech/EggAI/refs/heads/main/docs/docs/assets/avatar/billing-agent.png" width="40"/>

- **Purpose**: Handles financial and payment inquiries
- **Key Features**:
  - Retrieves billing information by policy number
  - Provides premium amounts and due dates
  - Updates payment information
  - Privacy controls (requires policy number)
- **Tools**: `get_billing_info`, `update_billing_info`

**See: [Billing Agent Documentation](../agents/billing/README.md)**

### Claims Agent
<img src="https://raw.githubusercontent.com/eggai-tech/EggAI/refs/heads/main/docs/docs/assets/avatar/claims-agent.png" width="40"/>

- **Purpose**: Manages insurance claims inquiries
- **Key Features**:
  - Retrieves claim status
  - Files new claims
  - Updates existing claims
  - Provides estimated payouts
- **Tools**: `get_claim_status`, `create_claim`, `update_claim`

**See: [Claims Agent Documentation](../agents/claims/README.md)**

### Policies Agent
<img src="https://raw.githubusercontent.com/eggai-tech/EggAI/refs/heads/main/docs/docs/assets/avatar/policies-agent.png" width="40"/>

- **Purpose**: Answers policy coverage questions using RAG
- **Key Features**:
  - Vector-based policy document search
  - Contextual answer generation
  - Multi-document retrieval
  - Vespa-powered search backend
- **API**: Also provides REST API on port 8003

**See: [Policies Agent Documentation](../agents/policies/README.md)**

### Escalation Agent
<img src="https://raw.githubusercontent.com/eggai-tech/EggAI/refs/heads/main/docs/docs/assets/avatar/escalation-agent.png" width="40"/>

- **Purpose**: Handles complex issues requiring human attention
- **Key Features**:
  - Multi-step escalation workflow
  - State-based conversation management
  - Support ticket creation
  - Handles complaints and technical issues
- **Workflow**: Reason → Details → Confirmation → Ticket Creation

**See: [Escalation Agent Documentation](../agents/escalation/README.md)**

### Audit Agent
<img src="https://raw.githubusercontent.com/eggai-tech/EggAI/refs/heads/main/docs/docs/assets/avatar/audit-agent.png" width="40"/>

- **Purpose**: Monitors and logs all system activity
- **Key Features**:
  - Captures all messages on `human` and `agents` channels
  - Categorizes messages by domain
  - Creates standardized audit records
  - Publishes to `audit_logs` channel

**See: [Audit Agent Documentation](../agents/audit/README.md)**

## Message Flow

1. User connects via WebSocket → **Frontend Agent**
2. User message → **Triage Agent** (classification)
3. Triage routes to appropriate specialized agent
4. Specialized agent processes and responds
5. Response flows back through Frontend to user
6. **Audit Agent** logs all interactions

## Running the Agents

See the main README.md for quick start instructions. Each agent can be run independently or as part of the full system.

## Testing

Each agent has its own test suite in `agents/{agent_name}/tests/`. Run tests with:

```bash
# Run all tests
make test

# Run tests for specific agent
make test-billing-agent
make test-claims-agent
make test-triage-agent
# ... and others
```

## Configuration

Agents are configured via environment variables with the pattern `{AGENT_NAME}_*`. See each agent's `config.py` for available settings.
