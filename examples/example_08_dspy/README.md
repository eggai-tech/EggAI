# Agent Evaluation and Enhancement Example for EggAI 🥚🤖

## **A Journey of Iterative Improvement**

Welcome to the **TriageAgent** example, where we demonstrate how iterative changes, new prompts, and **DSPy** optimization can refine a multi-agent system’s classification performance. Below is an outline of how our three classifier versions (V1, V2, and V3) evolved to produce better routing decisions within an **insurance support** context.

---

## **Initial Approach: Classifier V1**

The first iteration **classifier_v1** started with minimal instructions—essentially a straightforward prompt guiding the Large Language Model to classify a conversation as destined for **PolicyAgent**, **TicketingAgent**, or **TriageAgent**.

- **Key Features**:
  - Basic Python code using **DSPy** with a standard prompt.
  - No system-level instructions or docstrings that describe context or fallback rules in detail.

- **Performance** (based on `src/reports/classifier_v1.html`):

  ```
  Date: 2025-01-08 09:15:34    Meta: classifier_v1

  Summary
  ------------
  Total Test Cases: 22
  Passed:          16
  Failed:          6
  Success Rate:    72.73%
  ```

  While **72.73%** is a decent start, there was room for improvement—especially given the complexity of insurance-related conversations.

---

## **Strengthening Context: Classifier V2**

To improve classification accuracy, we introduced **system prompts** and **docstrings** in the **DSPy** signature as a way to provide clearer instructions and domain context. This included:

1. **Explicit Role Description**: Outlining the agent’s role in routing conversations to **PolicyAgent**, **TicketingAgent**, or **TriageAgent**.  
2. **Fallback Rules**: Emphasizing that uncertain insurance-related queries go to **TicketingAgent** and non-insurance queries go to **TriageAgent**.  
3. **Usage of Docstrings**: Leveraging them as part of the system prompt for the LLM.

- **Performance** (based on `src/reports/classifier_v2.html`):

  ```
  Date: 2025-01-08 09:15:34    Meta: classifier_v2

  Summary
  ------------
  Total Test Cases: 22
  Passed:          18
  Failed:          4
  Success Rate:    81.82%
  ```

  This update lifted our success rate to **81.82%**—a significant improvement, simply by clarifying the classification logic in the system prompt.

---

## **Optimizing with DSPy: Classifier V3**

To push performance further, we employed **DSPy’s optimization** features on a **training dataset**. Specifically, we used:

- **`dspy.BootstrapFewShot`**: A method that automatically selects the best prompt examples from the training set, iteratively refining them through a chain-of-thought approach.
- **Evaluation Pipeline**: After the optimization, we tested the newly-trained prompt on the **same 22 examples** from our “test set” to measure final performance.

- **Performance** (based on `src/reports/classifier_v3.html`):

  ```
  Date: 2025-01-08 09:15:34    Meta: classifier_v3

  Summary
  ------------
  Total Test Cases: 22
  Passed:          21
  Failed:          1
  Success Rate:    95.45%
  ```

  With DSPy’s help, **Classifier V3** reached a **95.45%** success rate—an excellent improvement over the previous versions.

---

## **Quality Gate with Pytest**

To ensure continued high performance, we set up a **quality gate** within our CI/CD pipeline using `pytest`. This gate will:

1. **Run all test conversations** through the classifier as part of the build process.
2. **Evaluate the success rate** (i.e., exact match of expected vs. actual target).
3. **Fail the pipeline** (and block merges) if the success rate **falls below** a chosen threshold (e.g., 50%, 80%, or 90%, depending on project requirements).

```python
@pytest.mark.asyncio
async def test_not_optimized_agent(monkeypatch):
    ...
    success_percentage = (success / total) * 100
    assert (success_percentage > 90), \
        f"Success rate {success_percentage:.2f}% is not greater than 90%."
```

By adjusting the assertion, you can enforce higher thresholds as your model’s performance improves.

---

## **How It All Comes Together**

1. **Dataset** (`triage-training.json`, `triage-testing.json`):
   - Realistic insurance conversation data for training and testing.

2. **Classifiers**:
   - **v1** (minimal instructions)
   - **v2** (enhanced system prompt and docstrings)
   - **v3** (fully optimized with `dspy.BootstrapFewShot`)

3. **Evaluation Scripts**:
   - Generate HTML reports detailing each test conversation, the expected routing vs. the actual routing, and pass/fail status.

4. **Quality Gate**:
   - Enforced via `pytest` and integrated into CI/CD, stopping merges that degrade the classification performance.

---

## **Getting Started**

1. **Install Dependencies**  
   ```bash
   pip install eggai litellm fastapi uvicorn pytest jinja2 python-dotenv dspy
   ```

2. **Set Up Environment Variable**  
   ```bash
   export OPENAI_API_KEY=your-api-key
   ```

3. **Run Tests**  
   ```bash
   pytest tests/test_triage_evaluation.py
   ```
   - This will generate a performance report (HTML) in the `reports/` directory.

4. **Optimize (Optional)**  
   - If you want to replicate the optimization process, run the DSPy scripts provided in the codebase. This will retrain and save the improved classifier.

---

## **Results and Reports**

Each classifier’s test run outputs an HTML report in `src/reports/` (or a configured location), summarizing:

- **Classifier V1**: 72.73% success.  
- **Classifier V2**: 81.82% success.  
- **Classifier V3**: 95.45% success.

Inspection of these reports shows how the addition of system prompts, docstring-based context, and eventually DSPy optimization each contributed to improved results.

---

## **Next Steps**

- **Refine the Dataset**: Incorporate more diverse conversations or corner cases.  
- **Tune the Quality Gate**: Increase the success-rate requirement to maintain high performance.  
- **Explore More DSPy Features**: Consider advanced optimization strategies (e.g., random search, multiple seeds).  
- **Integrate Feedback**: Employ real-world user data to continuously enhance the classifier’s routing accuracy.

---

## **Conclusion**

Through three iterations of classifier tuning, we moved from a basic approach to a robust, near-accurate system. DSPy’s optimization proved instrumental in reaching **95.45%** accuracy. With a CI-based quality gate in place, the **TriageAgent** can reliably grow and adapt—ensuring that only improvements make their way into production.

Thank you for exploring this **Agent Evaluation and Enhancement** journey with EggAI! 🥚🤖 We hope these examples inspire you to develop and continuously refine intelligent agents that seamlessly route and handle user interactions.