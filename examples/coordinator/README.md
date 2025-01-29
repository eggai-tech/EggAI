# Multi-Agent Communication with Human and Agent Channels

This example demonstrates a workflow involving two communication channels and multiple agents.

Key features include:

- **Human-Agent Interaction**: The Human Channel connects users with agents.
- **Coordinator Role**: The Coordinator Agent manages workflows and task delegation.
- **Specialized Agents**: Worker agents handle specific tasks, such as order processing and email notifications.
- **Event-Driven Design**: Real-time updates and notifications via the Human Channel.

Here is a simplified architecture overview:

![architecture-advanced-example.png](../../https://raw.githubusercontent.com/eggai-tech/EggAI/refs/heads/main/docs/docs/assets/architecture-coordinator.svg)

- **Human Channel**: Allows users or frontends to send and receive workflow-related data.
- **Agent Channel**: Manages message passing and events between agents.
- **Coordinator Agent** orchestrates communication between the Human Channel and worker agents.
- **Agent 1** acts as an **Email Agent**.
- **Agent 2** acts as an **Order Agent**.

The example code is available [here](https://github.com/eggai-tech/EggAI/tree/main/examples/coordinator).

## Prerequisites

Ensure you have the following dependencies installed:

- **Python** 3.10+
- **Docker** and **Docker Compose**

## Setup Instructions

Clone the EggAI repository:

```bash
git clone git@github.com:eggai-tech/EggAI.git
```

Move into the examples/getting_started folder:

```bash
cd examples/coordinator
```

Create and activate a virtual environment:

```bash
python -m venv venv
source venv/bin/activate  # For Windows: venv\\Scripts\\activate
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

Example output:

```plaintext
[COORDINATOR]: action message received. Forwarding to agents channel.
Agent is running. Press Ctrl+C to stop.
[ORDER AGENT]: order_requested event received. Emitting order_created event.
[EMAIL AGENT]: order_created event received. Sending email to customer.
[EMAIL AGENT]: order_created event received. Sending notification event.
[ORDER AGENT]: order_created event received.
[COORDINATOR]: human=true message received. Forwarding to human channel.
[COORDINATOR]: Received notification for human: Order created, you will receive an email soon.
```

What happens:

1. **Request Sent via Human Channel**:

   - The `main.py` script sends a request to create an order (e.g., `Laptop`, quantity `1`).

2. **Coordinator Agent Orchestrates Workflow**:

   - The Coordinator Agent processes the request and assigns tasks to worker agents:
     - **Order Agent**: Creates the order.
     - **Email Agent**: Sends an email notification.

3. **Notification Sent to Human Channel**:
   - Once the task is completed, the Coordinator Agent notifies the Human Channel.

## Clean Up

Stop and clean up the Docker containers:

```bash
docker compose down -v
```

## Next Steps

Explore additional resources:

- **Advanced Examples:** Discover more complex use cases in the [examples](https://github.com/eggai-tech/EggAI/tree/main/examples/) folder.
- **Contribution Guidelines**: Learn how to contribute to EggAI.
- **GitHub Issues**: [Report bugs or request features](https://github.com/eggai-tech/eggai/issues).
- **Documentation**: Refer to the official docs for deeper insights.
