# LangChain Tool Calling Agent

this example demonstrates integrating **LangChain** tool calling into an agent workflow using the `eggai` SDK.

Key features:

- LangChain Tool Integration
- Event-Driven Execution
- Simple Single-Agent Setup

The code for the example can be found [here](https://github.com/eggai-tech/EggAI/tree/main/examples/langchain-tool-calling).

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

Move into the `examples/langchain-tool-calling` folder:

```bash
cd examples/langchain-tool-calling
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
[EMAIL AGENT Result]: [{'name': 'count_emails', 'args': {'last_n_days': 5}, 'id': 'call_V74b9bHqYCFUApTk8ndw2hif', 'type': 'tool_call', 'output': 10}]
```

What happens:

- The Email Agent starts and subscribes to "email_prompt_requested" events.
- The main.py script publishes an event with a prompt like "How many emails did I get in the last 5 days?"
- The Email Agent receives the prompt, passes it to the LangChain pipeline, and if the LLM decides to call the count_emails tool, the tool is executed.
- The final answer, including the computed number of emails, is printed to the console.

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
