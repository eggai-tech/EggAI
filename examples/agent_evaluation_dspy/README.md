# Agent Evaluation and Optimization with DSPy

This example shows how to iterative improve an agent using DSPy. It shows the evolution (V1, V2, and V3) of a multi-agent system's classification performance in an insurance support context.

Key features:

- Iterative enhancements using **DSPy** optimization
- Multiple classifier versions: **V1**, **V2**, **V3**
- Improved classification logic with system prompts, docstrings, and fallback rules
- **CI/CD** integration using a quality gate enforced via **pytest**
- Real-world **insurance support** scenario for conversation routing

The code for this example is available [here](https://github.com/eggai-tech/EggAI/tree/main/examples/agent_evaluation_dspy).

## Classifier Evolution (V1, V2, and V3)

### Initial Approach: Classifier V1

- **Minimal Prompting**: A simple prompt directing the Large Language Model to classify a conversation for **PolicyAgent**, **TicketingAgent**, or **TriageAgent**.
- **Performance** (from [V1 Report](tests/reports/classifier_v1.html)):

```plaintext
Date: 2025-01-10 16:20:22 Meta: classifier_v1

Summary
------------
Total Test Cases: 22
Passed: 18
Failed: 4
Success Rate: 81.82%
```

Despite reaching **81.82%**, the approach lacked depth in instructions, leading to misclassifications for more complex queries.

### Strengthening Context: Classifier V2

- **Enhanced System Prompts & Docstrings**:
  - Detailed agent roles (for **PolicyAgent**, **TicketingAgent**, **TriageAgent**).
  - Fallback rules and insurance context clearly stated.
  - Docstrings used as part of the system prompt for the LLM.
- **Performance** (from [V2 Report](tests/reports/classifier_v2.html)):

```plaintext
Date: 2025-01-10 16:20:30 Meta: classifier_v2

Summary
------------
Total Test Cases: 22
Passed: 19
Failed: 3
Success Rate: 86.36%
```

By clarifying the classification logic, **Classifier V2** improved to **86.36%**.

### Optimizing with DSPy: Classifier V3

- **DSPy’s BootstrapFewShot**: Automated selection and refinement of the best prompt examples from the training set.
- **Performance** (from [V3 Report](tests/reports/classifier_v3.html)):

```plaintext
Date: 2025-01-10 16:20:38 Meta: classifier_v3

Summary
------------
Total Test Cases: 22
Passed: 21
Failed: 1
Success Rate: 95.45%
```

With **Classifier V3**, accuracy jumped to **95.45%**, showcasing the power of DSPy optimization.

## Quality Gate with Pytest

A quality gate is integrated into **CI/CD** using `pytest`:

```python
@pytest.mark.asyncio
async def test_not_optimized_agent(monkeypatch):
    ...
    success_percentage = (success / total) * 100
    assert (success_percentage > 90), \
        f"Success rate {success_percentage:.2f}% is not greater than 90%."
```

This setup fails the pipeline if performance dips below the specified threshold (e.g., **90%**).
In our case, **Classifier V3** surpassed this benchmark, ensuring its deployment readiness.

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

Move into the `examples/agent_evaluation_dspy` folder:

```bash
cd examples/agent_evaluation_dspy
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

## Run the Tests

```bash
pytest
```

This generates an HTML performance report in the `reports/` directory.  
It will run the triage evaluation on the configured classifier with the dataset found at `datasets/triage-testing.csv`.

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
