# Getting Started

Learn how to create two agents and setup the communication using the `eggai` SDK.

Key features:

- **Agent Collaboration:** Two agents working together in an event-driven environment.
- **Asynchronous Execution:** Agents are designed to process tasks concurrently, ensuring efficiency.
- **Scalable Infrastructure:** Powered by Kafka for reliable messaging and streaming.

Here is a simplified architecture overview:

![architecture-getting-started.svg](../../https://raw.githubusercontent.com/eggai-tech/EggAI/refs/heads/main/docs/docs/assets/architecture-getting-started.svg)

The code for the example can be found [here](https://github.com/eggai-tech/EggAI/tree/main/examples/getting_started). Let's dive in.

## Prerequisites

Ensure you have the following dependencies installed:

- **Python** 3.10+
- **Docker** and **Docker Compose**

## Setup Instructions

Clone the EggAI repository:

```bash
git clone git@github.com:eggai-tech/EggAI.git
```

Move into the `examples/getting_started` folder:

```bash
cd examples/getting_started
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
Agent is running. Press Ctrl+C to stop.
[ORDER AGENT]: Received request to create order. defaultdict(<function Agent._handle_messages.<locals>.<lambda> at 0x1046642c0>, {'event_name': 'order_requested', 'payload': {'product': 'Laptop', 'quantity': 1}})
[EMAIL AGENT]: Received order created event. defaultdict(<function Agent._handle_messages.<locals>.<lambda> at 0x104664b80>, {'event_name': 'order_created', 'payload': {'product': 'Laptop', 'quantity': 1}})
[ORDER AGENT]: Received order created event. defaultdict(<function Agent._handle_messages.<locals>.<lambda> at 0x104665da0>, {'event_name': 'order_created', 'payload': {'product': 'Laptop', 'quantity': 1}})
^CTask was cancelled. Cleaning up...
Done.
```

What happens:

- Agent 1 sends a message to Agent 2.
- Agent 2 processes the message and sends a response.
- The framework handles message passing, retries, and logging.

<img src="../../https://raw.githubusercontent.com/eggai-tech/EggAI/refs/heads/main/docs/docs/assets/redpanda-console.png" alt="Redpanda Console"/>

Congratulations! You've successfully run your first EggAI Multi-Agent application.

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
