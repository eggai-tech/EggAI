# Integrating LiteLLM with EggAI Framework 🧪🫶

Welcome to the **05-litellm-agent** example for **EggAI**! This example demonstrates how to integrate LiteLLM into the EggAI framework, showcasing how to handle customer inquiries in a structured and scalable way using two AI agents: **SupportAgent** and **EscalationAgent**. These agents collaborate to provide responses to customer queries, escalating issues when necessary.

---

## **What’s Inside?** 🗂️

**LiteLlmAgent**:
- An agent class based on the EggAI framework’s Agent class.
- Provides a completion wrapper function for seamless interaction with language models.
- Supports calling tools for enhanced functionality and task-specific operations.

**SupportAgent**:
- Uses a system prompt to handle common customer inquiries such as return policies, shipping times, and product information.
- Leverages LiteLLM to determine whether it can respond or if the issue needs escalation.
- Utilizes the `GetKnowledge` tool to query a simulated knowledge base.

**EscalationAgent**:
- Handles more complex issues by creating support tickets.
- Notifies the user and the support team about the ticket.
- Uses the `TicketingTool` to simulate ticket creation.

### **Flow** 🌊

The example simulates a customer inquiry system with two agents: SupportAgent and EscalationAgent. The agents interact with each other and the customer through channels. The flow is as follows:

#### **Customer Inquiry**:
   - A customer sends a question, such as "What is your return policy?" or "I have a billing issue."
   - The inquiry is published on the `humans` channel.

#### **SupportAgent**:
   - Listens for inquiries and processes the question.
   - Uses the `GetKnowledge` tool to fetch relevant information from the knowledge base.
   - If the issue is straightforward, it responds directly to the customer.
   - If the issue is complex, it escalates to the EscalationAgent.

#### **EscalationAgent**:
   - Listens for escalated inquiries.
   - Creates a support ticket for the issue using the `TicketingTool`.
   - Publishes the ticket details to the `agents` channel.
   - Informs the customer about the escalation and provides a ticket ID.

---

## **Prerequisites** 🔧

Before running this example, ensure you have the following:

### Step 1: Install Dependencies

```bash
pip install eggai litellm
```

### Step 2: Start Services with Docker

This example uses a messaging broker. Start the necessary services:

```bash
docker compose up -d
```

---

## **Running the Example** 🏆

Navigate to the `examples/05-litellm-agent` folder and run the main script:

```bash
python main.py
```

## **Expected output** 📤

```plaintext
Handling customer inquiry: What is your return policy?
Agent is running. Press Ctrl+C to stop.
Handling customer inquiry: I have a billing issue that isn't resolved yet.
Querying knowledge base for: return_policy
Response from SupportAgent: {'response': 'Our return policy is 30 days from the date of purchase. Items must be in their original condition.'}
Responding directly to the customer...
Querying knowledge base for: billing_issue
Response from SupportAgent: {'response': 'escalate'}
Escalating issue to EscalationAgent...
Creating support ticket for issue: I have a billing issue that isn't resolved yet.
Ticket created for escalated issue:  {'ticket_id': 'TCKT1188', 'department': 'Billing Department'}
```
---

## Architecture Overview 🔁

1. **User Query**: Customers send inquiries (e.g., "What is your return policy?").
2. **SupportAgent**: Handles general inquiries using a knowledge base or escalates complex issues.
3. **EscalationAgent**: Creates support tickets for escalated issues and notifies customers.
4. **Channels**:
   - **Humans Channel**: For interactions between customers and agents.
   - **Agents Channel**: For communication between agents.

---

## Code Breakdown 🔬

### Key Components

1. **LiteLlmAgent Initialization**:
   - `SupportAgent` and `EscalationAgent` are initialized with system prompts and model configurations.

2. **Tools**:
   - `GetKnowledge`: Used by the SupportAgent to query a simulated knowledge base.
   - `TicketingTool`: Used by the EscalationAgent to simulate ticket creation.

3. **Message Handling**:
   - Agents subscribe to channels and listen for specific message types.
   - Context is passed seamlessly between agents using structured messages.

4. **Main Script**:
   - Simulates both simple and complex customer inquiries.
   - Manages agent lifecycle and cleanup.

---

## Cleaning Up ❌

When you’re done, stop the services:

```bash
docker compose down -v
```

---

## Next Steps 🚀

- **Explore**: Try modifying the example to include additional agents or tools.
- **Learn More**: Check out other examples in the `examples` folder for advanced patterns.
- **Contribute**: Share your feedback, report issues, or contribute to the EggAI project.

---

Thank you for exploring how LiteLLM integrates into EggAI to create efficient, context-aware multi-agent systems! 🙏🧪

