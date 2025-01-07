# Agent Evaluation and Enhancement Example for EggAI 🥚🤖

## **A Story of Refinement and Improvement**

In the quest to build intelligent and responsive multi-agent systems, continuous evaluation and enhancement of each agent's performance are paramount. The **Agent Evaluation and Enhancement** example for **EggAI** embodies this journey. Focused on refining the **TriageAgent**, this example demonstrates how to:

1. **Assess agent effectiveness** using an evaluation dataset and test code.  
2. **Optimize agent performance** using **DSPy** (including a step-by-step optimization flow).  
3. **Establish quality gates** in CI/CD to enforce a desired success threshold and streamline agent performance improvements.

---

## **Building on Proven Foundations**

To create a robust evaluation framework, we integrated key components from previous EggAI examples:

- **WebSocket Gateway (`examples/02-websocket-gateway`)**:  
  - **Purpose**: Facilitates real-time communication between agents and users.  
  - **Integration**: Provides the communication backbone for sending and receiving test messages during evaluation.

- **LiteLlmAgent (`examples/05-litellm-agent`)**:  
  - **Purpose**: Enables efficient interaction with language models.  
  - **Integration**: Powers the **TriageAgent**, allowing it to process and respond to user messages accurately.

- **Triage Concept (`examples/06-multi-agent-conversation`)**:  
  - **Purpose**: Implements intelligent routing of user messages to appropriate agents.  
  - **Integration**: Serves as the foundation for enhancing the **TriageAgent**'s decision-making capabilities.

---

## **What’s Inside?** 🗂️

### **Agent Evaluation Framework**

- **Test Code (`tests/test_triage_evaluation.py`)**:  
  - **Functionality**: Automates the testing of the **TriageAgent** against a predefined JSON dataset (e.g., `triage-training.json`).  
  - **Features**:  
    - Parses user-agent conversations.  
    - Mocks message publishing to simulate agent responses.  
    - Validates the **TriageAgent**’s ability to correctly route messages.  
    - Records success and failure outcomes.  

- **Dataset (`datasets/triage-training.json`)**:  
  - **Content**: A collection of conversation samples with expected routing targets.  
  - **Purpose**: Serves as the benchmark for evaluating the **TriageAgent**’s performance.  

- **Reporting Tools**:  
  - **JSON Results**: Logs detailed test outcomes for further analysis.  
  - **HTML Report**: Generates a user-friendly report highlighting test successes and failures, enabling users to identify and address weaknesses in the **TriageAgent**.

### **Enterprise-Grade Agent Quality and Optimization with DSPy**

1. **Initial Evaluation (Not Optimized)**  
   - Running the default classifier (without DSPy optimization) yielded an **initial success rate of ~59%** in our sample tests.  
   - Example of unoptimized report: [Triage Not Optimized (59%)](triage-not-optimized.html).

2. **DSPy Evaluation and Metric**  
   - We define a simple metric that checks **exact match**: if the `expected_target` is equal to the `actual_target`, the test result is **PASS**; otherwise, **FAIL**.

3. **DSPy Optimization**  
   - **BootstrapFewShotWithRandomSearch**: Uses the training set to explore various prompt configurations and to automatically sample between 1 and 20 traces per predictor.  
   - Seeks to improve overall accuracy through a series of candidate prompt sets.  
   - **Example optimization output** (gradually improving from ~68% to 100%):  
     ```
     New best score: 68.18 for seed -3
     ...
     New best score: 95.45 for seed 0
     ...
     New best score: 100.0 for seed 3
     ```
   - Final optimized output: [Triage Optimized (100%)](triage-optimized.html)

4. **Quality Gate in CI/CD**  
   - **Pytest Integration**: The success percentage must exceed a threshold (e.g., 50% or higher) for the test suite to pass.  
   - **SonarQube Integration** (optional): Generate `lcov` or other coverage reports to be analyzed by SonarQube, ensuring continuous monitoring of agent performance over time.

---

## **How It Works** 🛠️

1. **Setup**:  
   - Ensure all dependencies are installed and services are running.

2. **Running Tests**:  
   - Execute the test script (e.g., `pytest tests/test_triage_agent.py` or `test_not_optimized_agent`) to evaluate the **TriageAgent** against the conversation dataset.

3. **Analyzing Results**:  
   - Review the console output for immediate feedback on each test case.  
   - Examine the generated HTML report for a comprehensive overview of the agent’s performance, including areas that need enhancement.  

4. **Enhancing & Optimizing the Agent**:  
   - Use the insights from the report to refine the **TriageAgent**’s logic, improve keyword detection, and optimize routing guidelines.  
   - Run **DSPy** optimization via [the provided script](#agent-optimization-script-snippet) for **BootstrapFewShotWithRandomSearch** to achieve better performance.

---

## **Running the Evaluation** 🏆

1. **Navigate to the Project Directory**:
   ```bash
   cd path/to/project-directory
   ```

2. **Execute the Test Script**:
   ```bash
   pytest tests/test_triage_agent.py
   ```
   - **Outcome**: The script will run through each conversation in the dataset, evaluate the **TriageAgent**’s routing decisions, and output the results.

3. **Access the HTML Report**:
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
from examples.example_08_dspy.src.classifier import classifier

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