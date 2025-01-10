# Multi-Agent Conversation Example for EggAI 🥚🤖

Welcome to the **06-multi-agent-conversation** example for **EggAI**! This example showcases how to build a collaborative multi-agent system using EggAI, where different agents work together to handle user inquiries efficiently. In this CLI Chat example, the **TriageAgent** routes user messages to the appropriate agents (**PolicyAgent**, **ClaimsAgent**, and **EscalationAgent**) to provide seamless and context-aware assistance.

Here is a simplified architecture overview:

![architecture-overview-img](../../docs/docs/assets/architecture-example-06-multi-agent-conversation.svg)

1. **User Interaction**: Users interact with the system through a CLI Chat interface.
2. **TriageAgent**: Analyzes incoming messages and routes them to the appropriate agent based on the content.
3. **PolicyAgent**: Handles policy-related inquiries using a mock `policies_database`.
4. **ClaimsAgent**: Manages claims-related inquiries and requests.
5. **EscalationAgent**: Takes care of issues that require human intervention by creating support tickets.
6. **Channels**:
   - **User Channel**: For interactions between the user and the agents.
   - **Agent Channel**: For communication and coordination between different agents.

The code for the example can be found [here](https://github.com/eggai-tech/EggAI/tree/main/examples/multi_agent_conversation).

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

Move into the `examples/multi_agent_conversation` folder:

```bash
cd examples/multi_agent_conversation
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

```plaintext
Welcome to the Insurance Customer Service System!

You: Hello, what's my policy's due date?

📄 PolicyAgent:
Hello! I'm here to help you with your policy inquiries. Could you please provide me with your **policy number**?
If you don't have it handy, your **full name** will work too, and I can look up the details for you.

You: A12345

📄 PolicyAgent:
Thank you for providing your policy number. Here are the details:

- **Policy Number:** A12345
- **Policyholder Name:** John Doe
- **Coverage Details:** Comprehensive
- **Premium Amount:** $500
- **Due Date:** January 1, 2025

If you have any more questions or need further assistance, feel free to ask!

You: I need info about claims

📝 ClaimsAgent:
Hello! I can assist you with inquiries related to claims. Could you please specify what information you need?
Some topics I can help with include filing a new claim, checking the status of a claim, or understanding claim coverage
and payouts. Let me know how I can assist you today!

You: Can u list my current claims?

📝 ClaimsAgent:
I can certainly help you with that. To proceed, could you please provide your claim ID or any relevant details
that might help in locating your claims? Once I have that information, I can check your current claims and provide you
with the necessary details.

You: Sorry I lost all my data, I don't remember

💬 EscalationAgent:
We have created a support ticket ESC-654321 for your issue. Our Claims Support team will reach out to you
shortly.

You: exit

Goodbye!
```

What happens:

- A user interacts with the CLI Chat by sending messages related to their insurance needs.
- TriageAgent:
  - Receives the user message and determines which agent should handle the request based on the content and context.
  - Routes the message to the PolicyAgent, ClaimsAgent, or EscalationAgent as appropriate.
- PolicyAgent / ClaimsAgent:
  - Processes the user inquiry and provides relevant information or assistance.
  - If the request is beyond their scope, they delegate the issue back to the TriageAgent for further handling.
- EscalationAgent:
  - Manages escalated issues by creating support tickets and notifying the user.
  - Ensures that complex or unresolved issues are directed to human support representatives.

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
