# EggAI: Advanced Agents with DSPy ReAct

This example demonstrates how to integrate a complex ReAct module into EggAI agents for dynamic question-answering
tasks. DSPy supports ReAct, an LLM agent designed to tackle complex tasks in an interactive fashion. ReAct is composed
of an iterative loop of interpretation, decision and action-based activities ("Thought, Action, and Observation") based
on an evolving set of input and output fields. Through this real-time iterative approach, the ReAct agent can both
analyze and adapt to its responses over time as new information becomes available. Below, we explain how the example
works step by step.

## Under the Hood

```python
 await agents_channel.publish({
        "type": "question",
        "payload": "Give me the year of construction of the Eiffel Tower summed with the year of construction of the Empire State Building."
    })
```

**Initialization of the ReAct Agent**: The `react_module` ReAct agent is initialized contains two tools: `evaluate_math` for
mathematical operations and `search_wikipedia` for retrieving relevant information from a ColBERTv2 model.

**Agent Input**: The agent receives a question: *"Give me the year of construction of the Eiffel Tower summed with the
year of construction of the Empire State Building."*

**First Thought**: The agent reasons: *"I need to find the years of construction for both the Eiffel Tower and the
Empire State Building in order to sum them."* It uses the `search_wikipedia` tool to query for construction years.

**Iterative Search**: The agent iteratively refines its search queries when initial results don’t contain the required
information. It tries broader and more specific queries, such as: *"Eiffel Tower construction year, Empire State
Building construction year."* *"Eiffel Tower construction year."* *"Empire State Building construction year."* *"Eiffel
Tower history construction year."*

**Observation and Refinement**: Each search produces observations, such as articles or snippets, which the agent
analyzes to determine if they contain the necessary information. When relevant data is missing, it generates a new
query.

**Reasoning and Calculation**: After retrieving sufficient information, the agent reasons: *"The construction year of
the Eiffel Tower is 1887, and the Empire State Building was constructed from 1930 to 1931. To find the total, I will sum
1887 and 1931 (the year it was completed)."* The agent uses the `evaluate_math` tool to calculate the sum: *1887 +
1931 = 3818.*

**Output**: The agent produces a final answer: *"3818"*, which is returned as the result.

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