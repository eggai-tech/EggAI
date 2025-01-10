# Advanced Use Case: Multi-Agent Communication with Human and Agent Channels

Learn how to use the `eggai` framework to orchestrate more complex workflows, bridging both human and agent communication channels. In this demo, a **Coordinator Agent** orchestrates the flow between the **Human Channel** and the worker agents (**Email Agent** and **Order Agent**).

Key features:

- **Human-Agent Interaction:** A Human Channel bridges the gap between users and agents.  
- **Coordinator Role:** The Coordinator Agent orchestrates workflows and delegates tasks to worker agents.  
- **Worker Agents:** Specialized agents handle specific tasks, like email notifications and order processing.  
- **Event-Driven Design:** Real-time updates and notifications via the Human Channel.

Here is the architecture diagram for this example:

![architecture-advanced-example.png](../../docs/docs/assets/architecture-coordinator.svg)

The code for the example can be found [here](https://github.com/eggai-tech/EggAI/tree/main/examples/01-coordinator). Let's dive in.

## Prerequisites

Ensure you have the following dependencies installed:

- **Python** 3.10+  
- **Docker** and **Docker Compose**

## Setup Instructions

Clone the EggAI repository:

```bash
git clone git@github.com:eggai-tech/EggAI.git
```

Move into the `examples/01-coordinator` folder:

```bash
cd examples/01-coordinator
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

Start Redpanda using Docker Compose:

```bash
docker compose up -d
```

## Run the Example

Run the main file to execute the workflow:

```bash
python main.py
```

Expected output:

```
[COORDINATOR]: action message received. Forwarding to agents channel.
Agent is running. Press Ctrl+C to stop.
[ORDER AGENT]: order_requested event received. Emitting order_created event.
[EMAIL AGENT]: order_created event received. Sending email to customer.
[EMAIL AGENT]: order_created event received. Sending notification event.
[ORDER AGENT]: order_created event received.
[COORDINATOR]: human=true message received. Forwarding to human channel.
[COORDINATOR]: Received notification for human:  Order created, you will receive an email soon.
```

What happens:

1. The Human Channel sends a request to create an order.  
2. The Coordinator Agent distributes tasks to the Order Agent and Email Agent.  
3. The Email Agent sends a notification event, which is then forwarded by the Coordinator Agent back to the Human Channel.

## Clean Up

When you're done, stop and clean up the Docker containers:

```bash
docker compose down -v
```

## Next Steps

Ready to explore further? Check out:

- **Advanced Examples:** Discover more complex use cases in the [examples](https://github.com/eggai-tech/EggAI/tree/main/examples/) folder.  
- **Contribution Guidelines:** Get involved and help improve EggAI!  
- **GitHub Issues:** [Submit a bug or feature request](https://github.com/eggai-tech/eggai/issues).  
- **Documentation:** Refer to the official docs for deeper insights.