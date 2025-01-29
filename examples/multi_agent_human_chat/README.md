# Multi-Agent Insurance Support System

This example shows a simple multi-agent system for insurance support. It combines a WebSocket gateway, lightweight language model agents, and a triage mechanism to deliver efficient and user-friendly support.

Here is a simplified architecture overview:

![architecture-getting-started.svg](https://raw.githubusercontent.com/eggai-tech/EggAI/refs/heads/main/docs/docs/assets/multi-agent-human-chat-2.svg)

- **User Interaction**: Engages with the system through a WebSocket-enabled chat interface.
- **TriageAgent**: Analyzes incoming messages and routes them to the appropriate agent based on content.
- **Agent 1**: PolicyAgent, handling policy-related inquiries using a mock `policies_database`.
- **Agent 2**: TicketingAgent, managing support ticket creation and retrieval for escalated issues.
- **Channels**:
  - **User Channel**: Facilitates interactions between the user and the agents.
  - **Agents Channel**: Enables communication and coordination among different agents.
- **WebSocket Gateway**: Oversees real-time communication between the FastAPI server and connected clients.

The code for the example can be found [here](https://github.com/eggai-tech/EggAI/tree/main/examples/multi_agent_human_chat).

## Prerequisites

Ensure you have the following dependencies installed:

- **Python** 3.10+
- **Docker** and **Docker Compose**

Ensure you have a valid OpenAI API key set in your environment:

```bash
export OPEN_AI_API_KEY="your-api-key"
```

## Setup Instructions

Clone the EggAI repository:

```bash
git clone git@github.com:eggai-tech/EggAI.git
```

Move into the `examples/multi_agent_human_chat` folder:

```bash
cd examples/multi_agent_human_chat
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

Upon running the example and accessing the chat interface at [http://localhost:8000](http://localhost:8000), you should see a web-based chat UI:

![Chat UI Screenshot](https://raw.githubusercontent.com/eggai-tech/EggAI/refs/heads/main/docs/docs/assets/example-07-chat.png)

### Sample Chat

1. **User** initiates the conversation:

   ```
   Hello, I need to check my policy details.
   ```

2. **TriageAgent** routes the message to **PolicyAgent**:

   ```
   📄 PolicyAgent:
   Hello! I'm here to help you with your policy inquiries. Could you please provide me with your **policy number**?
   If you don't have it handy, your **full name** will work too, and I can look up the details for you.
   ```

3. **User** provides the policy number:

   ```
   A12345
   ```

4. **PolicyAgent** responds with policy details:

   ```
   📄 PolicyAgent:
   Thank you for providing your policy number. Here are the details:

   - **Policy Number:** A12345
   - **Policyholder Name:** John Doe
   - **Coverage Details:** Comprehensive
   - **Premium Amount:** $500
   - **Due Date:** January 1, 2025

   If you have any more questions or need further assistance, feel free to ask!
   ```

5. **User** requests support for a billing issue:

   ```
   I need help with a billing issue.
   ```

6. **TriageAgent** routes the message to **TicketingAgent**:
   ```
   💬 TicketingAgent:
   We have created a support ticket ESC-0001 for your issue. Our Billing team will reach out to you shortly.
   ```

## Cleaning Up

Stop and remove Docker containers:

```bash
docker compose down -v
```

## Next Steps

- **Extend Functionality**: Add new agents or tools to handle more complex workflows.
- **Connect Real Data**: Integrate the system with external databases or APIs.
- **Enhance UI**: Improve the chat interface with features like authentication and message history.
- **Learn More**: Explore other examples in the `examples` folder for advanced patterns.
- **Contribute**: Share feedback or improvements with the EggAI community.
