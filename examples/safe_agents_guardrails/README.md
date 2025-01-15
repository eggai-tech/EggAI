# Safe Agents with Guardrails.ai

Large Language Model (LLM) agents are powerful tools capable of responding to various user queries—whether trivial,
complex, or potentially harmful. However, unguarded AI systems can inadvertently produce inappropriate, toxic, or
misleading content. **Guardrails** become essential here to ensure that LLM outputs stay within acceptable boundaries,
preserving both user trust and brand integrity.

Below is a visualization of how an agent without guards compares to one with guardrails in place:

![Without vs. With Guardrails](https://raw.githubusercontent.com/guardrails-ai/guardrails/main/docs/img/with_and_without_guardrails.svg)  
*Source: [Guardrails.ai](https://github.com/guardrails-ai/guardrails)*

In this example, we show how to build an LLM-powered agent that is **guarded** against unwanted or harmful outputs. We
use **[Guardrails.ai](https://github.com/ShreyaR/guardrails)** for toxicity filtering and **DSPy** for core language
model functionalities. We also added **PII Masking** with Presidio, ensuring sensitive data (like emails) is replaced
with `<EMAIL_ADDRESS>` before further processing:

![Presidio Detection Flow](https://microsoft.github.io/presidio/assets/detection_flow.gif)  
*Source: [Microsoft Presidio](https://microsoft.github.io/presidio)*

The result is a multi-agentic system that can handle user queries responsibly while maintaining a high level of safety
and reliability. Code for this example is available
[here](https://github.com/eggai-tech/EggAI/tree/main/examples/safe_agents_guardrails).

## Overview of the Approach

**Input Guard**: The `answers_agent` subscribes to new messages on the `agents` channel. Upon receiving a
`"question"`,
we:

Check PII: If emails are found, they are masked with `<EMAIL_ADDRESS>` (via Presidio).
Check Toxicity: If the text is still deemed toxic, we publish an `INPUT_GUARDRAIL` error and stop processing.

**Answer Generation**: If the input is safe, the agent calls `wiki_qa(question=question)` to generate an answer.
This specialized module searches an offline Wikipedia corpus to provide relevant information.

**Output Guard**: We run the toxicity check again on the generated answer. If the answer is flagged, we publish an
`OUTPUT_GUARDRAIL` error, preventing any harmful content from reaching the user.

**Publishing the Result**: If both the question and answer pass guardrails, the safe, validated answer is published
   back to the `agents` channel for consumption by other parts of the system.

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

Move into the `examples/litellm_agent` folder:

```bash
cd examples/litellm_agent
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
guardrails configure
guardrails hub install hub://guardrails/toxic_language
```

Start [Redpanda](https://github.com/redpanda-data/redpanda) using Docker Compose:

```bash
docker compose up -d
```

## Run the Example

```bash
python main.py
```

## Run Tests

```bash
pytest
```

**Expected behaviour**  
Watch the console for the agent’s answer to the test questions:

- The first query involves a math-related, Wikipedia-augmented question.
- The second query (“Are you stupid??”) is caught by the toxicity filter, returning a safe fallback response.
- An example with an email address in the question will show masked output (`<EMAIL>`).

## Next Steps

- **Additional Guards**: Check out [Guardrails.ai’s documentation](https://github.com/ShreyaR/guardrails) to chain
  multiple guards for diverse content moderation needs.
- **Scale Out**: Integrate with more advanced DSPy pipelines or domain-specific systems (e.g., CRM, knowledge bases).
- **CI/CD Testing**: Use `pytest` or similar to maintain performance and safety standards through version upgrades.
- **Contribute**: [Open an issue](https://github.com/eggai-tech/eggai/issues) or submit a pull request on **EggAI** to
  enhance our guardrails example!

Enjoy creating **safe**, **scalable**, and **versatile** LLM-powered agents! For any issues, reach out via GitHub
or the EggAI community.