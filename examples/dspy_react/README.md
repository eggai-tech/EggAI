# ReActive Agents with DSPy

This example demonstrates how to integrate DSPy’s powerful *ReAct* module into EggAI agents for dynamic, real-time question-answering tasks.
*ReAct* enables agents to tackle complex problems by continuously refining their responses through an iterative cycle of reasoning (*Thought*), decision-making (*Action*), and feedback (*Observation*). As the agent processes information, it adjusts its actions based on ongoing observations, allowing it to adapt and improve over time. This flexible, real-time iterative approach makes ReAct ideal for tasks that require dynamic reasoning, rapid decision-making, and continuous adaptation to new information.

The code for this example is available [here](https://github.com/eggai-tech/EggAI/tree/main/examples/dspy_react).

## How it works

In this example, we test the ReAct agent by sending a question to the agent channel.
The agent dynamically processes the question and iteratively refines its responses.

For example:

```python
 await agents_channel.publish({
        "type": "question",
        "payload": "Give me the year of construction of the Eiffel Tower summed with the year of construction of the Empire State Building."
    })
```

### Available tools
The `react_module` ReAct contains two tools:
- `evaluate_math`: Handles mathematical operations.
- `search_wikipedia` Retrieves relevant information from a ColBERTv2 model.

### Agent Input
The agent receives the question: _"Give me the year of construction of the Eiffel Tower summed with the year of construction of the Empire State Building."_

### First Thought
The agent begins by reasoning: _"I need to find the years of construction for both the Eiffel Tower and the Empire State Building in order to sum them."_ It uses the `search_wikipedia` tool to gather relevant data.

### Iterative Search
The agent iteratively refines its search queries when initial results don’t contain the required
information. It tries broader and more specific queries, such as: _"Eiffel Tower construction year, Empire State
Building construction year."_ _"Eiffel Tower construction year."_ _"Empire State Building construction year."_ _"Eiffel
Tower history construction year."_

**Observation and Refinement**: Each search produces observations, such as articles or snippets, which the agent
analyzes to determine if they contain the necessary information. When relevant data is missing, it generates a new
query.

**Reasoning and Calculation**: After retrieving sufficient information, the agent reasons: _"The construction year of
the Eiffel Tower is 1887, and the Empire State Building was constructed from 1930 to 1931. To find the total, I will sum
1887 and 1931 (the year it was completed)."_ The agent uses the `evaluate_math` tool to calculate the sum: _1887 +
1931 = 3818._

**Output**: The agent produces a final answer: _"3818"_, which is returned as the result.

## Key Takeaways

This example illustrates the power of integrating DSPy’s ReAct framework into EggAI agents. By leveraging iterative
reasoning and dynamic tool usage, the agent can:

- Adapt its queries based on observations.
- Combine tools (e.g., mathematical evaluation and information retrieval) for complex reasoning.
- Deliver accurate and context-aware results.

The result is a robust and flexible system capable of handling diverse and challenging tasks with minimal hardcoding.

## Prerequisites

- **Python** 3.10+
- **Docker** and **Docker Compose**
- Valid OpenAI API key in your environment:
  ```bash
  export OPEN_AI_API_KEY="your-api-key"
  ```

## Setup Instructions

Clone the EggAI repository:

```bash
git clone git@github.com:eggai-tech/EggAI.git
```

Move into the `examples/dspy_react` folder:

```bash
cd examples/dspy_react
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

## Run the Tests

```bash
pytest
```

## Next Steps

- **Additional Guards**: Check out [Guardrails.ai’s documentation](https://github.com/ShreyaR/guardrails) to chain
  multiple guards for diverse content moderation needs.
- **Scale Out**: Integrate with more advanced DSPy pipelines or domain-specific systems (e.g., CRM, knowledge bases).
- **CI/CD Testing**: Use `pytest` or similar to maintain performance and safety standards through version upgrades.
- **Contribute**: [Open an issue](https://github.com/eggai-tech/eggai/issues) or submit a pull request on **EggAI** to
  enhance our guardrails example!

Enjoy creating **safe**, **scalable**, and **versatile** LLM-powered agents! For any issues, reach out via GitHub
or the EggAI community.
