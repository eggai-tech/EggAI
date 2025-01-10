# Multi-Agent Communication with Human, WebSocket, and Agent Channels

This example demonstrates real-time event-driven communication between humans, WebSocket gateways, and agents.

Key features:

- **Real-Time Communication**: Enables live, bidirectional interaction between users and the agent ecosystem through WebSocket.
- **Scalable Coordination**: The Coordinator Agent dynamically routes tasks and events.
- **Event-Driven Workflow**: Agents respond to specific events, providing flexibility and extensibility.
- **Separation of Concerns**: Each agent has a clear role for easier customization and extension.

Here is a simplified architecture overview:

![architecture-advanced-example.png](../../docs/docs/assets/architecture-gateway.svg)

- **WebsocketGateway Agent**: Bridges human interfaces (e.g., web UI) and the agent ecosystem via WebSocket.
- **Coordinator Agent**: Routes messages and orchestrates the workflow.
- **Agent 1**: Order Agent, handling order lifecycle events.
- **Agent 2**: Email Agent, managing notifications and email communication.

The code for the example can be found [here](https://github.com/eggai-tech/EggAI/tree/main/examples/websocket_gateway).

## Prerequisites

- **Python** 3.10+
- **Docker** and **Docker Compose**

## Setup Instructions

Clone the EggAI repository:

```bash
git clone git@github.com:eggai-tech/EggAI.git
```

Move into the `examples/websocket_gateway` folder:

```bash
cd examples/websocket_gateway
```

Create and activate a virtual environment:

```bash
python -m venv venv
source venv/bin/activate  # For Windows: venv\Scripts\activate
```

Install the required dependencies:

```bash
pip install -r requirements.txt
```

Start [Redpanda](https://github.com/redpanda-data/redpanda) using Docker Compose:

```bash
docker compose up -d
```

## Run the Example

```bash
python main.py
```

Expected output:

```
Connection id: {"connection_id":"15b3a00b-41c0-467c-b411-8557dff2fab7"}
Message id: b6ad3608-2ce2-4c53-a123-45e9eec797cf
[ORDER AGENT]: order_requested event received. Emitting order_created event.
[EMAIL AGENT]: order_created event received. Sending email to customer.
[EMAIL AGENT]: order_created event received. Sending notification event.
[ORDER AGENT]: order_created event received.
Reply: {"id":"b6ad3608-2ce2-4c53-a123-45e9eec797cf","type":"notification","payload":{"message":"Order created, you will receive an email soon."}}
Agent is running. Press Ctrl+C to stop.
[WEBSOCKET GATEWAY]: WebSocket connection 15b3a00b-41c0-467c-b411-8557dff2fab7 closed.
```

What happens:

1. A request (e.g., `order_requested` for a `Laptop`) is sent via the Human Channel or WebsocketGateway Agent.
2. The Coordinator Agent broadcasts the request to the Agent Channel.
3. The Order Agent processes the request and emits an `order_created` event.
4. The Email Agent sends a notification and emits a `notification` event.
5. The WebsocketGateway Agent streams `notification` events back to the frontend.

## Clean Up

Stop and clean up the Docker containers:

```bash
docker compose down -v
```

## Next Steps

Ready to explore further? Check out:

- **Advanced Examples:** Discover more complex use cases in the [examples](https://github.com/eggai-tech/EggAI/tree/main/examples/) folder.
- **Contribution Guidelines:** Get involved and help improve EggAI!
- **GitHub Issues:** [Submit a bug or feature request](https://github.com/eggai-tech/eggai/issues).
- **Documentation:** Refer to the official docs for deeper insights.
