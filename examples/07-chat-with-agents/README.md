# Multi-Agent Insurance Support System Example for EggAI 🥚🤖

Welcome to the **Multi-Agent Insurance Support System** example for **EggAI**! This example demonstrates how to build a collaborative multi-agent system using EggAI, where different agents work together to handle user inquiries efficiently. In this example, the **TriageAgent** routes user messages to the appropriate agents (**PolicyAgent** and **TicketingAgent**) to provide seamless and context-aware assistance through a WebSocket-enabled FastAPI server with a user-friendly chat interface.

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

### **TicketingAgent**:
- Manages support ticket creation and retrieval for issues that require escalation.
- Creates unique support tickets and informs users that their issue will be escalated to a human support representative.
- Utilizes a mock `ticket_database` to store and manage support tickets.

### **TriageAgent**:
- Acts as the central router for user messages.
- Analyzes user inquiries and directs them to the appropriate agent (**PolicyAgent** or **TicketingAgent**) based on predefined guidelines.
- Ensures that requests are handled by the most suitable agent or escalated when necessary.

### **FastAPI Server with WebSocket Integration**:
- Provides a WebSocket interface for real-time communication between users and the multi-agent system.
- Manages WebSocket connections and routes messages through the agent channels.
- Serves an HTML chat interface (`chat.html`) accessible via a web browser.

### **Flow** 🌊

The example simulates a multi-agent conversation system where user messages are intelligently routed to the appropriate agents for handling. The flow is as follows:

#### **User Interaction**:
- A user interacts with the system through a WebSocket-enabled chat interface by sending messages related to their insurance needs.

#### **TriageAgent**:
- Receives the user message and determines which agent should handle the request based on the content and context.
- Routes the message to the **PolicyAgent** or **TicketingAgent** as appropriate.

#### **PolicyAgent**:
- Processes policy-related inquiries and provides relevant information or assistance.
- If the request is beyond their scope, they delegate the issue back to the **TriageAgent** for further handling.

#### **TicketingAgent**:
- Manages escalated issues by creating support tickets and notifying the user.
- Ensures that complex or unresolved issues are directed to human support representatives.

---

## **Prerequisites** 🔧

Before running this example, ensure you have the following:

### Step 1: Install Dependencies

```bash
pip install eggai litellm fastapi uvicorn
```

### Step 2: Start Services with Docker

This example uses a messaging broker. Start the necessary services:

```bash
docker compose up -d
```

---

## **Running the Example** 🏆

Navigate to the project directory and run the main script:

```bash
python main.py
```

This will start the FastAPI server on `http://127.0.0.1:8000/` with WebSocket support at `ws://127.0.0.1:8000/ws`.

### **Access the Chat Interface**

Open your web browser and navigate to [http://127.0.0.1:8000/](http://127.0.0.1:8000/) to access the chat UI. The interface allows you to interact with the multi-agent system in real-time.

---

## **Expected Output** 📤

Upon running the example and accessing the chat interface, you should see a web-based chat UI similar to the screenshot below:

![Chat UI Screenshot](/docs/assets/example-07-chat.png)

### **Sample Interaction**

1. **User** connects via the web chat interface and sends a message:
    ```
    Hello, I need to check my policy details.
    ```

2. **TriageAgent** processes the message and routes it to **PolicyAgent**:
    ```
    📄 PolicyAgent:
    Hello! I'm here to help you with your policy inquiries. Could you please provide me with your **policy number**?
    If you don't have it handy, your **full name** will work too, and I can look up the details for you.
    ```

3. **User** responds with their policy number:
    ```
    A12345
    ```

4. **PolicyAgent** retrieves and displays policy details:
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

5. **User** requests to create a support ticket:
    ```
    I need help with a billing issue.
    ```

6. **TriageAgent** routes the message to **TicketingAgent**:
    ```
    💬 TicketingAgent:
    We have created a support ticket ESC-0001 for your issue. Our Billing team will reach out to you shortly.
    ```

---

## **Architecture Overview** 🔁

![architecture-overview-img](../../docs/assets/architecture-insurance-support-system.svg)

1. **User Interaction**: Users interact with the system through a WebSocket-enabled chat interface.
2. **TriageAgent**: Analyzes incoming messages and routes them to the appropriate agent based on the content.
3. **PolicyAgent**: Handles policy-related inquiries using a mock `policies_database`.
4. **TicketingAgent**: Manages support ticket creation and retrieval for escalated issues.
5. **Channels**:
   - **User Channel**: For interactions between the user and the agents.
   - **Agents Channel**: For communication and coordination between different agents.
6. **WebSocket Gateway**: Manages real-time communication between the FastAPI server and connected clients.

---

## **Code Breakdown** 🔬

### **Key Components**

1. **LiteLlmAgent Initialization**:
   - **TriageAgent**, **PolicyAgent**, and **TicketingAgent** are initialized with specific system prompts and model configurations.

2. **Mock Databases**:
   - `policies_database`: A simulated database containing policy information for demonstration purposes.
   - `ticket_database`: A simulated database for managing support tickets.

3. **Tools**:
   - **get_policy_details**: A tool used by the PolicyAgent to retrieve policy information from the `policies_database`.
   - **create_ticket** and **retrieve_ticket**: Tools used by the TicketingAgent to manage support tickets.

4. **Triage System Prompt**:
   - Defines guidelines for the TriageAgent to determine which agent should handle each user request based on keywords and context.

5. **Message Handling**:
   - Users interact via the web chat interface, and messages are processed by the TriageAgent, which routes them to the appropriate agent.
   - Agents communicate through structured messages, ensuring context is maintained throughout the conversation.

6. **FastAPI Server**:
   - Manages WebSocket connections and routes messages through the agent channels.
   - Serves an HTML interface (`chat.html`) for user interaction.

7. **WebSocket Manager**:
   - Handles connection management, message routing, and maintaining message caches for each user connection.

8. **Main Script (`main.py`)**:
   - Initializes agents, sets up channels, and starts the FastAPI server with WebSocket support.
   - Manages the lifecycle of the WebSocket gateway and agent subscriptions.

---

## **Cleaning Up** ❌

When you’re done, stop the services:

```bash
docker compose down -v
```

This command will stop and remove the Docker containers and associated volumes.

---

## **Next Steps** 🚀

- **Explore**: Modify the example to include additional agents or enhance existing ones with more tools and capabilities.
- **Integrate**: Connect the system to a real database or external services for dynamic data retrieval and storage.
- **Enhance UI**: Improve the `chat.html` interface for a better user experience with features like authentication and message history.
- **Learn More**: Check out other examples in the `examples` folder to discover advanced multi-agent patterns and integrations.
- **Contribute**: Share your feedback, report issues, or contribute to the EggAI project to help improve the framework.

---

Thank you for exploring the **Multi-Agent Insurance Support System** example for EggAI! 🥚🤖 We hope this example helps you understand how to build and manage collaborative multi-agent systems to handle complex user interactions effectively. 🙏✨