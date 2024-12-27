# Multi-Agent Conversation Example for EggAI 🥚🤖

Welcome to the **06-multi-agent-conversation** example for **EggAI**! This example showcases how to build a collaborative multi-agent system using EggAI, where different agents work together to handle user inquiries efficiently. In this CLI Chat example, the **TriageAgent** routes user messages to the appropriate agents (**PolicyAgent**, **ClaimsAgent**, and **EscalationAgent**) to provide seamless and context-aware assistance.

---

## **What’s Inside?** 🗂️

### **LiteLlmAgent**:
- An agent class based on the EggAI framework’s Agent class.
- Facilitates communication with language models through a completion wrapper function.
- Supports integrating tools for task-specific operations and enhanced functionality.

### **PolicyAgent**:
- Handles inquiries related to insurance policies, such as coverage details, premiums, and policy modifications.
- Utilizes a mock `policies_database` to retrieve and provide policy information.
- Ensures responses are polite, concise, and within the scope of policy-related queries.

### **ClaimsAgent**:
- Manages claims-related inquiries, including filing new claims, checking claim statuses, and understanding claim coverage or payouts.
- Provides clear instructions and maintains an empathetic tone.
- Escalates complex or out-of-scope requests to the **TriageAgent**.

### **EscalationAgent**:
- Handles issues that cannot be resolved by the PolicyAgent or ClaimsAgent.
- Creates support tickets and informs users that their issue will be escalated to a human support representative.
- Generates a unique ticket ID and specifies the relevant department for the issue.

### **TriageAgent**:
- Acts as the central router for user messages.
- Analyzes user inquiries and directs them to the appropriate agent based on predefined guidelines.
- Ensures that requests are handled by the most suitable agent or escalated when necessary.

### **Flow** 🌊

The example simulates a multi-agent conversation system where user messages are intelligently routed to the appropriate agents for handling. The flow is as follows:

#### **User Interaction**:
- A user interacts with the CLI Chat by sending messages related to their insurance needs.

#### **TriageAgent**:
- Receives the user message and determines which agent should handle the request based on the content and context.
- Routes the message to the **PolicyAgent**, **ClaimsAgent**, or **EscalationAgent** as appropriate.

#### **PolicyAgent / ClaimsAgent**:
- Processes the user inquiry and provides relevant information or assistance.
- If the request is beyond their scope, they delegate the issue back to the **TriageAgent** for further handling.

#### **EscalationAgent**:
- Manages escalated issues by creating support tickets and notifying the user.
- Ensures that complex or unresolved issues are directed to human support representatives.

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

Navigate to the `examples/06-multi-agent-conversation` folder and run the main script:

```bash
python main.py
```

---

## **Expected Output** 📤

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

---

## **Architecture Overview** 🔁

![architecture-overview-img](../../docs/assets/architecture-example-06-multi-agent-conversation.svg)

1. **User Interaction**: Users interact with the system through a CLI Chat interface.
2. **TriageAgent**: Analyzes incoming messages and routes them to the appropriate agent based on the content.
3. **PolicyAgent**: Handles policy-related inquiries using a mock `policies_database`.
4. **ClaimsAgent**: Manages claims-related inquiries and requests.
5. **EscalationAgent**: Takes care of issues that require human intervention by creating support tickets.
6. **Channels**:
   - **User Channel**: For interactions between the user and the agents.
   - **Agent Channel**: For communication and coordination between different agents.

---

## **Code Breakdown** 🔬

### **Key Components**

1. **LiteLlmAgent Initialization**:
   - **PolicyAgent**, **ClaimsAgent**, **EscalationAgent**, and **TriageAgent** are initialized with specific system prompts and model configurations.
   
2. **Mock Database**:
   - `policies_database`: A simulated database containing policy information for demonstration purposes.

3. **Tools**:
   - **get_policy_details**: A tool used by the PolicyAgent to retrieve policy information from the `policies_database`.

4. **Triage System Prompt**:
   - Defines guidelines for the TriageAgent to determine which agent should handle each user request based on keywords and context.

5. **Message Handling**:
   - Users interact via the CLI, and messages are processed by the TriageAgent, which routes them to the appropriate agent.
   - Agents communicate through structured messages, ensuring context is maintained throughout the conversation.

6. **Main Script**:
   - Manages the lifecycle of the CLI Chat, initializes agents, and handles user inputs and agent responses.

---

## **Cleaning Up** ❌

When you’re done, stop the services:

```bash
docker compose down -v
```

---

## **Next Steps** 🚀

- **Explore**: Modify the example to include additional agents or enhance existing ones with more tools and capabilities.
- **Learn More**: Check out other examples in the `examples` folder to discover advanced multi-agent patterns and integrations.
- **Contribute**: Share your feedback, report issues, or contribute to the EggAI project to help improve the framework.

---

Thank you for exploring the **06-multi-agent-conversation** example for EggAI! 🥚🤖 We hope this example helps you understand how to build and manage collaborative multi-agent systems to handle complex user interactions effectively. 🙏✨