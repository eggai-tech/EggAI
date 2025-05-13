# Frontend Agent

## Overview

The Frontend Agent manages WebSocket connections between users and the backend AI system. It serves as the communication bridge, routing user messages to appropriate backend agents and delivering responses back to users in real-time.

## Key Features

- Handles real-time WebSocket-based communication
- Routes user messages to appropriate backend agents
- Delivers agent responses back to users
- Manages connection state and message caching
- Supports optional content moderation via Guardrails

## Architecture

### Core Components

- **Agent Module** (`agent.py`): Core implementation managing the message flow
- **Config** (`config.py`): Configuration settings for the agent
- **WebSocket Manager** (`websocket_manager.py`): Handles WebSocket connections and communication
- **Guardrails** (`guardrails.py`): Optional content moderation capabilities

### Frontend Capabilities

The agent serves as the primary interface between users and the backend AI system:

- **WebSocket Management**: Maintains active connections with users through real-time WebSockets
- **Message Routing**: Directs user messages to the appropriate backend agents for processing
- **Response Delivery**: Returns agent responses to the correct user sessions
- **Connection Management**: Handles session tracking and maintenance for consistent user experiences
- **Content Moderation**: Optional guardrails for filtering inappropriate content

### Communication Flow

1. User connects via WebSocket (handled by WebSocket Manager)
2. User messages are processed by the Frontend Agent
3. Messages are routed to the Triage Agent for classification
4. Responses from backend agents are delivered back through WebSockets
5. Connection state is maintained throughout the session

## Technical Details

### WebSocket Management

The WebSocket Manager maintains active connections with:
- Connection storage by unique ID
- Asynchronous message processing
- Heartbeat monitoring
- Error handling for disconnections

```python
async def connect(websocket):
    connection_id = str(uuid.uuid4())
    connections[connection_id] = websocket
    return connection_id
```

### Message Routing

Messages flow through the system as follows:
1. Frontend Agent receives messages from WebSocket connections
2. Initial messages are sent to the Triage Agent for classification
3. Triage Agent routes to specialized agents (Billing, Claims, etc.)
4. Responses from agents are sent back through Frontend Agent

### Guardrails Integration

Optional content moderation can be enabled through the Guardrails module:
- Input validation and sanitization
- Content filtering for harmful content
- Response appropriateness checks

## Development

### Testing

Test the Frontend Agent with:
```bash
make test-frontend-agent
```

### Extending

To extend the Frontend Agent:
1. Update WebSocket handlers for new message types
2. Add new routing logic as needed
3. Enhance guardrails for specific requirements
4. Test with mock WebSocket connections

### Public Assets

Static assets for web interfaces are stored in the `public/` directory:
- Web interface HTML templates
- CSS and JavaScript files
- Configuration files

## Integration Points

- **Web Clients**: Connects directly with user browsers via WebSockets
- **Triage Agent**: The first agent in the processing chain for user messages
- **All Backend Agents**: Receives responses from and forwards messages to other agents