# Agent Evaluation and Enhancement Example for EggAI

A journey of iterative improvement—welcome to the **TriageAgent** example, where we showcase how iterative changes, new prompts, and **DSPy** optimization can refine a multi-agent system’s classification performance in an **insurance support** context. Below is an overview of how our three classifier versions (V1, V2, and V3) evolved to produce better routing decisions.

## Key Features

- Iterative enhancements using **DSPy** optimization  
- Multiple classifier versions: **V1**, **V2**, **V3**  
- Improved classification logic with system prompts, docstrings, and fallback rules  
- **CI/CD** integration using a quality gate enforced via **pytest**  
- Real-world **insurance support** scenario for conversation routing  

## Classifier Evolution

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

Despite reaching **72.73%**, the approach lacked depth in instructions, leading to misclassifications for more complex queries.

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

By clarifying the classification logic, **Classifier V2** improved to **81.82%**.

### Optimizing with DSPy: Classifier V3

- **DSPy’s BootstrapFewShot**: Automated selection and refinement of the best prompt examples from the training set.  
- **Evaluation Pipeline**: The newly-trained prompt was tested on the same 22 examples, yielding:

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

- **Python** 3.10+  
- **Docker** and **Docker Compose**  
- **An OpenAI API Key** (for LLM usage)

## Setup Instructions

Clone the EggAI repository:

```bash
git clone https://github.com/eggai-tech/EggAI.git
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

(Optional) Start Docker services if required by your environment, for instance:

```bash
docker compose up -d
```

## Run the Tests

```bash
pytest
```

This generates an HTML performance report in the `reports/` directory.  
It will run the triage evaluation on the configured classifier with the dataset found at `datasets/triage-testing.csv`.

## (Optional) Optimize with DSPy

If you want to replicate the optimization process:

1. Ensure your **OpenAI** API key is set:

   ```bash
   export OPENAI_API_KEY=your-api-key
   ```
2. Run the **DSPy** scripts provided in the codebase to retrain and save the improved classifier.  

## Results and Reports

- **Classifier V1**: 81.82% success ([Full Report](tests/reports/classifier_v1.html))  
- **Classifier V2**: 86.36% success ([Full Report](tests/reports/classifier_v2.html))  
- **Classifier V3**: 95.45% success ([Full Report](tests/reports/classifier_v3.html))

## Next Steps

- **Refine the Dataset**: Add more diverse or corner-case scenarios.  
- **Tune the Quality Gate**: Increase the minimum success-rate requirement in `pytest` as performance improves.  
- **Explore Advanced DSPy Features**: Consider random search or multiple seeds for further tuning.  
- **Incorporate Real-World Feedback**: Continuously enhance the classifier with real conversation data.

## Conclusion

Through three iterations—V1, V2, and V3—the **TriageAgent** improved from a basic classifier (81.82%) to a high-performing one (95.45%). By leveraging system prompts, docstrings, and DSPy’s optimizers, plus enforcing a quality gate, your EggAI-based agents can reliably evolve and excel in complex routing tasks.