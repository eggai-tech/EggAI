# LangChain Tool Calling Agent 🤖

This example demonstrates how to integrate **LangChain** tools into an **EggAI** agent workflow. By binding external tools to the language model, your agent can perform more complex operations—like counting emails over a certain period—directly from within a natural language prompt.

## Overview 🔄

In this scenario, we have a single **Email Agent** that:

1. Listens for "email_prompt_requested" events.
2. Uses LangChain and a bound tool to process the user's query (e.g., "How many emails did I get in the last 5 days?").
3. Leverages the tool to compute an answer and return it to the user.

### Key Features Highlighted

- **LangChain Tool Integration**: Seamlessly connect an external function (`count_emails`) to the LLM.
- **Event-Driven Execution**: The agent reacts when it receives an "email_prompt_requested" event.
- **Single-Agent Simplicity**: Focus on one agent’s workflow to understand how to add capabilities through tools.

---

## Prerequisites 🔧

Before you begin, ensure you have the following:

- **Python** 3.10+
- **Docker** and **Docker Compose**

If you’re using OpenAI’s `ChatOpenAI`, ensure you have a valid OpenAI API key. Set it as an environment variable:

```bash
export OPENAI_API_KEY=your-api-key
```

---

## Setup Instructions ⏳

### Step 1: Create a Virtual Environment (Optional but Recommended) 🌍

To avoid dependency conflicts, create and activate a virtual environment:

```bash
python -m venv venv
source venv/bin/activate  # For Windows: venv\\Scripts\\activate
```

### Step 2: Install Dependencies 🎓

Install the EggAI framework and LangChain libraries:

```bash
pip install eggai langchain langchain-openai
```

### Step 3: Start Required Services with Docker 🚢

Spin up any required services, such as Redpanda for message brokering:

```bash
docker compose up -d
```

This will:
- Run the Redpanda broker for event-based communication.

---

## Running the Example 🏆

Navigate to the `examples/03-langchain-tool-calling` directory (if not already there) and run:

```bash
python main.py
```

### What Happens Next?

1. **Agent Initialization**:  
   The Email Agent starts and subscribes to "email_prompt_requested" events.

2. **Prompt Publication**:  
   The `main.py` script publishes an event with a prompt like "How many emails did I get in the last 5 days?"

3. **LLM + Tool Execution**:  
   The Email Agent receives the prompt, passes it to the LangChain pipeline, and if the LLM decides to call the `count_emails` tool, the tool is executed.

4. **Result Delivery**:  
   The final answer, including the computed number of emails, is printed to the console.

### Example Output

```plaintext
Agent is running. Press Ctrl+C to stop.
[EMAIL AGENT Result]: [{'name': 'count_emails', 'args': {'last_n_days': 5}, 'id': 'call_V74b9bHqYCFUApTk8ndw2hif', 'type': 'tool_call', 'output': 10}]
```

---

## Stopping and Cleaning Up ❌

When you're done, bring down the Docker environment to free up resources:

```bash
docker compose down -v
```

---

## Next Steps 🚀

- **Explore More Examples:** Check out the `examples/` folder for additional use cases and advanced workflows.
- **Get Involved:** Contribute to EggAI by following our contribution guidelines.
- **Open Issues or Suggest Features:** [File an issue on GitHub](https://github.com/eggai-tech/eggai/issues) if you encounter bugs or want to request new functionalities.
- **Dive into the Documentation:** Explore the official docs to understand all configuration options, architectural best practices, and performance tuning tips.

For more resources:

- **EggAI Documentation**: Visit [GitHub](https://github.com/eggai-tech/eggai) for official docs.
- **LangChain Documentation**: Learn more about tool integration and prompt templates.
- **OpenAI API Reference**: Optimize your model parameters and prompts.

Happy coding! 🤖🥚