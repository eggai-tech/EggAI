# Tool Calling with ReAct Agents in DSPy

This example demonstrates how to integrate tool calling capabilities from the _ReAct_ module of DSPy into EggAI agents for dynamic, real-time question-answering tasks.

_ReAct_ enables agents to tackle complex problems by continuously refining their responses through an iterative cycle of reasoning (_Thought_), decision-making (_Action_), and feedback (_Observation_). As the agent processes information, it adjusts its actions based on ongoing observations, allowing it to adapt and improve over time. This flexible, real-time iterative approach makes ReAct ideal for tasks that require dynamic reasoning, rapid decision-making, and continuous adaptation to new information.

The code for this example is available [here](https://github.com/eggai-tech/EggAI/tree/main/examples/tool_calling).

## How it works

In this example, we test the ReAct agent by sending a question to the agent channel.
The agent dynamically processes the question and iteratively refines its responses.

For example:

```python
message = Message(
    type="question",
    source="main",
    data={"message": "what's the result of 12345 multiplied by 54321?"},
)
await agents_channel.publish(message)
```

### Available tools

The `react_module` contains the following tool:

- `execute_python_code`: Executes Python code and returns the result.

## Prerequisites

- **Python** 3.10+
- **Docker** and **Docker Compose**

### Language Model Options

You can use either OpenAI or LM Studio for this example:

#### Option 1: OpenAI

Set a valid OpenAI API key in your environment:

```bash
OPENAI_API_KEY=<your_openai_api_key>
REACT_AGENT_LANGUAGE_MODEL=openai/gpt-4o-mini
```

#### Option 2: LM Studio

1. Download and install [LM Studio](https://lmstudio.ai/)
2. Start a local server with your chosen model
3. Set the environment variables:

```bash
LM_STUDIO_API_BASE=http://localhost:1234/v1/
LM_STUDIO_API_KEY=lm-studio
REACT_AGENT_LANGUAGE_MODEL_API_BASE=http://localhost:1234/v1/
REACT_AGENT_LANGUAGE_MODEL=lm_studio/mistral-nemo-instruct-2407
```

## Setup Instructions

Clone the EggAI repository:

```bash
git clone git@github.com:eggai-tech/EggAI.git
```

Move into the `examples/tool_calling` folder:

```bash
cd examples/tool_calling
```

Create and activate a virtual environment and install the required dependencies:

```bash
make setup
```

Start [Redpanda](https://github.com/redpanda-data/redpanda) using Docker Compose:

```bash
docker compose up -d
```

## Run the Example

```bash
make start-all
```

## Example output

```bash
==== User Question ====
Question: what's the result of 12345 multiplied by 54321?
=======================

Result: 670592745

==== Agent Response ====
Answer: The result of the multiplication is 670592745.
Numeric: 670592745.0
Reasoning: To solve this problem, I multiplied 12345 by 54321.
=======================
```

## Run the Tests

```bash
pytest
```

## Next Steps

- **Contribute**: [Open an issue](https://github.com/eggai-tech/eggai/issues) or submit a pull request on **EggAI** to
  enhance our guardrails example!

Enjoy creating **safe**, **scalable**, and **versatile** LLM-powered agents! For any issues, reach out via GitHub
or the EggAI community.
