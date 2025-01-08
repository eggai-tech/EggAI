# Agent Evaluation and Enhancement Example for EggAI 🥚🤖

## **A Story of Refinement and Improvement**

Imagine a multi-agent landscape where messages must reach the correct destination every time. Our **TriageAgent** began with a straightforward goal: route user conversations reliably. Initial tests—guided by a dedicated JSON dataset and automated checks—revealed a commendable start yet uncovered gaps in accuracy.

Enter **DSPy**, transforming experiments into breakthroughs. With a simple metric (exact match of expected vs. actual targets) and **BootstrapFewShotWithRandomSearch**, the TriageAgent advanced from a modest **59% success rate** \([view report](triage-not-optimized.html)\) to a remarkable **100%** \([view report](triage-optimized.html)\). A CI/CD quality gate now ensures these gains stand firm by enforcing a minimum success threshold and preventing performance regressions.

---

## **Building on Proven Foundations**

This progress builds on earlier EggAI work:

- **WebSocket Gateway** for real-time testing and message flow.
- **LiteLlmAgent** for swift, model-driven responses.
- **Triage Concept** for orchestrating how multi-agent conversations unfold.

Together, they anchor the TriageAgent’s architecture, paving the way for efficient routing and reliable outcomes.

---

## **What’s Inside?** 🗂️

Within this example, a clear testing framework checks how well the TriageAgent matches each conversation to its intended agent, using data from **`triage-training.json`**. Test results are saved in JSON form and showcased in an HTML report, pinpointing precisely where improvements can be made.

Meanwhile, a DSPy optimization script details how we refined the TriageAgent’s logic. By iteratively sampling prompts and configurations, the agent surged to an optimal state—ready for production and ongoing enhancements.

---

## **A Glimpse of DSPy Optimization**

1. **Metric**: We rely on exact matches for pass/fail.
2. **Random Search**: The agent tests diverse prompt strategies with different seeds, aiming for incremental gains.
3. **Progress**: Climbing from 59% (see [not-optimized report](triage-not-optimized.html)) to 100% (see [optimized report](triage-optimized.html)).
   ```Going to sample between 1 and 20 traces per predictor.
    Will attempt to bootstrap 16 candidate sets.
    Average Metric: 15.00 / 22 (68.2%): 100%|██████████| 22/22 [00:00<00:00, 9053.64it/s]
    New best score: 68.18 for seed -3
    Scores so far: [68.18]
    .... OMITTED
    Best score so far: 95.45
    36%|██████████| 22/22 [00:13<00:22,  1.64s/it]
    Bootstrapped 22 full traces after 8 examples for up to 1 rounds, amounting to 8 attempts.
    Average Metric: 22.00 / 22 (100.0%): 100%|██████████| 22/22 [00:03<00:00,  6.64it/s]
    New best score: 100.0 for seed 3
    Scores so far: [68.18, ...,  86.36, 90.91, 95.45, 90.91, 86.36, 100.0]
    Best score so far: 100.0
   ```
   - Final optimized output: [Triage Optimized (100%)](triage-optimized.html)
4. **Quality Gate**: Pytest assertions and CI checks protect against regressions, ensuring that performance remains above a chosen threshold (e.g., 50% or higher).

## **How It Works** 🛠️

1. **Setup**:

   - Ensure all dependencies are installed and services are running.

2. **Running Tests**:

   - Execute the test script (e.g., `pytest tests/test_triage_evaluation.py` or `test_not_optimized_agent`) to evaluate the **TriageAgent** against the conversation dataset.

3. **Analyzing Results**:

   - Review the console output for immediate feedback on each test case.
   - Examine the generated HTML report for a comprehensive overview of the agent’s performance, including areas that need enhancement.

4. **Enhancing & Optimizing the Agent**:
   - Use the insights from the report to refine the **TriageAgent**’s logic, improve keyword detection, and optimize routing guidelines.
   - Run [**DSPy**](https://dspy.ai/learn/optimization/optimizers/) optimization using BootstrapFewShotWithRandomSearch to achieve better performance.

---

## **Prerequisites** 🔧

Ensure you have a valid OpenAI API key. Set it as an environment variable:

```bash
export OPENAI_API_KEY=your-api-key
```

### Install Dependencies\*\*

```bash
pip install eggai litellm fastapi uvicorn pytest jinja2 python-dotenv dspy
```

---

## **Running the Evaluation** 🏆

1. **Execute the Test Script**:

   ```bash
   pytest tests/test_triage_evaluation.py
   ```

   - **Outcome**: The script will run through each conversation in the dataset, evaluate the **TriageAgent**’s routing decisions, and output the results.

2. **Access the HTML Report**:
   After the tests complete, an HTML report will be generated in the `reports` directory. Open the report in your web browser to review detailed results:
   ```bash
   open reports/YYYYMMDD-HHMMSS-triage-agent-report.html
   ```

---

## **Agent Optimization Script Snippet**

Below is an example of how DSPy is integrated to **optimize** our classification approach:

```python
import json
import dspy
from dotenv import load_dotenv
from dspy import MIPROv2
from dspy.teleprompt import BootstrapFewShotWithRandomSearch
from examples.example_08_dspy.src.classifiers.v1 import classifier


def load_data(path: str = "../datasets/triage-training.json"):
    with open(path, "r") as f:
        ds_data = json.load(f)
    devset = []
    for ex in ds_data:
        devset.append(
            dspy.Example(
                chat_history=ex["conversation"],
                target_agent=ex["target"]
            ).with_inputs("chat_history")
        )
    return devset


def metric(example, pred, trace=None) -> bool:
    return example.target_agent.lower() == pred.target_agent.lower()


def run_evaluation(program, devset):
    evaluator = dspy.evaluate.Evaluate(
        devset=devset,
        num_threads=10,
        display_progress=True,
        return_outputs=True,
        return_all_scores=True
    )
    score, results, all_scores = evaluator(program, metric=metric)
    print("Final score:", score)


def optimize(trainset):
    teleprompter = BootstrapFewShotWithRandomSearch(
        metric=metric,
        max_labeled_demos=20,
        num_threads=20,
        max_bootstrapped_demos=20
    )
    optimized_program = teleprompter.compile(classifier, trainset=trainset)
    optimized_program.save("optimized_classifier_bootstrap.json")
    run_evaluation(optimized_program, trainset)


def main():
    load_dotenv()
    devset = load_data()
    # Evaluate current classifier (unoptimized)
    run_evaluation(classifier, devset)
    # Optimize using DSPy
    optimize(devset)


if __name__ == "__main__":
    main()
```

- **Key steps**:
  - **Define a metric** (exact match).
  - **Use DSPy** to run a random search, bootstrapping different prompt configurations.
  - **Identify the best seed** that yields the highest success rate (up to 100%).
  - **Save** the optimized version and re-run evaluation.

---

## **Expected Output** 📤

Upon running the tests and optimizations, you will observe:

- **Console Output**:

  - A log of each test case indicating **PASS** or **FAIL**, along with pertinent details.
  - A summary showing the total number of tests, successes, failures, and the overall success rate.
  - Incremental improvements in success rate during the DSPy optimization process.

- **HTML Report**:
  - A visually appealing and interactive report detailing each test case.
  - Sections highlighting the summary of results and detailed insights into each conversation’s outcome.
  - Indicators for successful and failed tests to quickly identify areas needing attention.

---

## **Architecture Overview** 🔁

1. **Test Execution**:

   - The test script sends predefined conversations to the **TriageAgent** via the WebSocket gateway.

2. **TriageAgent Processing**:

   - Analyzes each conversation to determine the appropriate target agent based on the content and context.

3. **Result Collection**:

   - The test script captures the **TriageAgent**’s routing decisions and compares them against expected outcomes.

4. **Reporting**:

   - Successes and failures are logged and compiled into a comprehensive HTML report for review and further enhancement.

5. **Optimization (DSPy)**:
   - Evaluates the classifier with a defined metric, then iteratively improves the prompt strategy to achieve higher success rates.

---

## **Code Breakdown** 🔬

### **Key Components**

1. **Test Script** (`tests/test_triage_agent.py` / `test_not_optimized_agent`)

   - **Functions**:
     - `parse_conversation`: Converts conversation text into structured message formats.
     - `test_handle_user_message`: Runs the evaluation by sending conversations to the **TriageAgent** and recording outcomes.
     - `generate_html_report`: Creates an HTML report using Jinja2 templates to visualize test results.

2. **Dataset** (`datasets/triage-training.json`)

   - Contains a variety of conversation scenarios to rigorously test the **TriageAgent**’s routing logic.

3. **Reporting Mechanism**

   - Utilizes Jinja2 for templating and Bootstrap for styling to produce an intuitive and informative HTML report.

4. **Agent Integration**

   - **TriageAgent** leverages the **LiteLlmAgent** for processing and decision-making, ensuring accurate and efficient message routing.

5. **DSPy Integration**
   - **BootstrapFewShotWithRandomSearch** uses the training set to find the best set of prompt examples and achieve higher success scores.

---

## **Cleaning Up** ❌

After completing your evaluations, gracefully shut down the services to free up resources:

```bash
docker compose down -v
```

- **Effect**: Stops and removes the Docker containers along with their associated volumes, ensuring no residual processes remain active.

---

## **Next Steps** 🚀

Elevate your agent evaluation and enhancement process with these actionable steps:

- **Refine the Dataset**: Expand the `triage-training.json` with more diverse conversation scenarios to further test the **TriageAgent**’s capabilities.
- **Enhance Reporting**: Customize the HTML report to include additional metrics, visualizations, or interactive elements for deeper insights.
- **Automate Enhancements**: Integrate the evaluation framework into a CI/CD pipeline to continuously assess and improve agent performance (see **Quality Gate in CI/CD**).
- **Expand Agent Capabilities**: Use the insights from evaluations to introduce new features or adjust existing ones, ensuring the **TriageAgent** adapts to evolving user needs.
- **Learn More**: Explore other EggAI examples to discover advanced testing methodologies and agent integration techniques.
- **Contribute**: Share your enhancements, report issues, or contribute new features to the EggAI project to support the community.

---

Thank you for embarking on the **Agent Evaluation and Enhancement** journey with EggAI! 🥚🤖 We hope this example empowers you to build more effective and intelligent agents, driving superior user interactions and system performance. 🙏✨
