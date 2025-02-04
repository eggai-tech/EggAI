# Multi-Agent Insurance Support System

AI agents collaborate to deliver efficient, personalized customer support.

This example shows a simple multi-agent system for insurance support.

The code for the example can be found [here](https://github.com/eggai-tech/EggAI/tree/main/examples/multi_agent_human_chat).

## User Interaction

Users interact with the system through a WebSocket-enabled chat interface.

![Chat UI Screenshot](https://raw.githubusercontent.com/eggai-tech/EggAI/refs/heads/main/docs/docs/assets/support-chat.png)

## Agents Overview

Autonomous agents collaborate with clear defined roles, objectives and skills.

### **TriageAgent**

**Role**: Analyze incoming messages and route them to the appropriate agent based on content.  
**Objective**: Ensure that user inquiries are efficiently assigned to the right agent.  
**Skill**: Content classification and routing.

### **PoliciesAgent**

**Role**: Handle policy-related inquiries using a mock `policies_database`.  
**Objective**: Provide accurate and detailed information about user policies.  
**Skill**: Policy management expertise.

### **BillingAgent**

**Role**: Assist customers with billing-related inquiries such as due amounts, billing cycles, and payment statuses.  
**Objective**: Resolve billing-related questions efficiently and provide updates to billing records as needed.  
**Skill**: Billing expertise and data management.

### **EscalationAgent**

**Role**: Manage support ticket creation and retrieval for escalated issues that other agents cannot resolve.  
**Objective**: Ensure unresolved issues are properly documented and assigned to the correct human support teams.  
**Skill**: Escalation management and ticket tracking.

### **WebSocketGatewayAgent**

**Role**: Oversee real-time communication between the FastAPI server and connected clients.  
**Objective**: Enable seamless interactions between users and agents through a WebSocket-enabled chat interface.  
**Skill**: Real-time communication, session management, and message handling.

## Architecture Overview

![architecture-getting-started.svg](https://raw.githubusercontent.com/eggai-tech/EggAI/refs/heads/main/docs/docs/assets/multi-agent-human-chat-2.svg)

## Getting Started

### Prerequisites

Ensure you have the following dependencies installed:

- **Python** 3.10>=3.12
- **Docker** and **Docker Compose**

Ensure you have a valid OpenAI API key and Guardrails AI token set in your environment:

```bash
export OPEN_AI_API_KEY="your-api-key"
export GUARDRAILS_TOKEN="your-guardrails-ai-token"
```

### Setup Instructions

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

Configure Guardrails:

```bash
guardrails configure --token $GUARDRAILS_TOKEN
guardrails hub install hub://guardrails/toxic_language
```

Start [Redpanda](https://github.com/redpanda-data/redpanda) using Docker Compose:

```bash
docker compose up -d
```

### Run the Example

```bash
python main.py
```

Upon running the example and accessing the chat interface at [http://localhost:8000](http://localhost:8000), you should see a web-based chat UI.

### Cleaning Up

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
