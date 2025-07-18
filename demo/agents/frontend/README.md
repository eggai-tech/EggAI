# Frontend Agent

The Frontend Agent provides a WebSocket gateway for real-time communication between users and the multi-agent system.

- **Purpose**: Manages WebSocket connections between users and backend
- **Key Features**:
  - Real-time bidirectional communication
  - Connection state management
  - Message buffering for offline connections
  - Optional content moderation via Guardrails
- **Channels**: Listens on `human`, publishes to `agents`

## Quick Start

```bash
# From the project root
make start-frontend

# Or run directly
python -m agents.frontend.main
```

The web interface will be available at http://localhost:8000

## Features

- WebSocket-based real-time communication
- Connection state management
- Message buffering for offline connections
- Optional content moderation via Guardrails
- FastAPI-based REST endpoints
- Built-in chat UI with support categories
- Clickable example questions for easy onboarding
- Dark mode support

## Configuration

Key environment variables:
```bash
FRONTEND_PROMETHEUS_METRICS_PORT=9090
FRONTEND_ENABLE_GUARDRAILS=false  # Enable content moderation
FRONTEND_GUARDRAILS_API_KEY=your-key  # If guardrails enabled
```

## API Endpoints

### WebSocket
- **URL**: `ws://localhost:8000/ws`
- **Protocol**: JSON messages

### REST Endpoints
- **GET** `/`: Chat UI interface
- **GET** `/health`: Health check endpoint
- **GET** `/metrics`: Prometheus metrics

## WebSocket Message Format

### Client to Server
```json
{
  "type": "user_message",
  "content": "What's my premium?",
  "connection_id": "unique-connection-id"
}
```

### Server to Client
```json
{
  "type": "agent_message",
  "content": "I can help with that...",
  "agent": "Billing",
  "connection_id": "unique-connection-id"
}
```

## Testing

```bash
# Run all frontend tests
make test-frontend-agent

# Test WebSocket connections
pytest agents/frontend/tests/test_agent.py -v

# Test guardrails integration
pytest agents/frontend/tests/test_config_guardrails.py -v
```

## Development

### Running with Guardrails

```bash
FRONTEND_ENABLE_GUARDRAILS=true \
FRONTEND_GUARDRAILS_API_KEY=your-key \
make start-frontend
```

### Custom UI Development

The chat UI is located in `agents/frontend/static/`:
- `index.html` - Main chat interface
- Modify styles and behavior as needed

### Message Flow

1. User connects via WebSocket
2. Messages are validated (optionally with Guardrails)
3. Published to `human` channel
4. Responses from agents on `human` channel
5. Forwarded back to user via WebSocket

## Architecture

- **Input**: WebSocket connections from users
- **Output Channel**: Publishes to `human` channel
- **Input Channel**: Listens on `human` channel for agent responses
- **Framework**: FastAPI with WebSocket support
- **Optional**: Guardrails AI for content moderation

## Monitoring

- Prometheus metrics: http://localhost:9090/metrics
- Connection count and message rates
- Guardrails validation metrics (if enabled)
- WebSocket connection health