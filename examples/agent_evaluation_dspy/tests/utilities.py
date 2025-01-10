import json
import os
from datetime import datetime

import dspy
from jinja2 import Environment, FileSystemLoader, select_autoescape

from ..datasets.loader import load_dataset


def load_data(file: str):
    """
    Loads the dataset and constructs the devset list of dspy.Example objects.

    :param path: Path to the triage-training JSON file.
    :return: A list of dspy.Example objects.
    """
    devset = []
    for ex in load_dataset(file):
        devset.append(
            dspy.Example(
                chat_history=ex["conversation"],
                target_agent=ex["target"]
            ).with_inputs("chat_history")
        )
    return devset


def run_evaluation(program, devset):
    """
    Runs evaluation of the classifier over the given devset.

    :param devset: A list of dspy.Example objects to evaluate against.
    """
    evaluator = dspy.evaluate.Evaluate(
        devset=devset,
        num_threads=10,
        display_progress=False,
        return_outputs=True,
        return_all_scores=True
    )
    score, results, all_scores = evaluator(program, metric=lambda example, pred,
                                                                  trace=None: example.target_agent.lower() == pred.target_agent.lower())
    return score, results


def generate_report(results, report_name):
    test_results = []
    for example, pred, score in results:
        test_results.append(
            {
                "conversation": example.chat_history,
                "expected_target": example.target_agent,
                "actual_target": pred.target_agent,
                "status": "PASS" if score else "FAIL",
                "confidence": pred.confidence,
                "reasoning": pred.reasoning,
            }
        )

    success_percentage = (len([r for r in test_results if r["status"] == "PASS"]) / len(test_results)) * 100
    summary = {
        "total": len(test_results),
        "success": len([r for r in test_results if r["status"] == "PASS"]),
        "failure": len([r for r in test_results if r["status"] == "FAIL"]),
        "success_percentage": f"{success_percentage:.2f}",
    }

    return write_html_report(test_results, summary, report_name)


def write_html_report(test_results, summary, report_name):
    abs_output_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "reports"))
    os.makedirs(abs_output_dir, exist_ok=True)

    env = Environment(
        loader=FileSystemLoader(searchpath="./"),
        autoescape=select_autoescape(["html", "xml"]),
    )

    template_str = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>EggAI - Performance Report - Triage Agent</title>
        <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css">
        <link rel="stylesheet" href="https://cdn.datatables.net/1.13.4/css/dataTables.bootstrap5.min.css">
        <style>
            body {
                padding: 20px;
            }
            .summary {
                margin-bottom: 30px;
            }
            .pass {
                color: green;
                font-weight: bold;
            }
            .fail {
                color: red;
                font-weight: bold;
            }
        </style>
    </head>
    <body>
        <div style="margin: 0 40px">
            <h1 class="mb-4">EggAI - Performance Report - Triage Agent</h1>
            <p><strong>Date:</strong> {{ current_date }} <span style="margin-left: 20px"><b>Meta:</b> {{ report_name }}</span></p>
            

            <div class="summary">
                <h3>Summary</h3>
                <ul>
                    <li>Total Test Cases: {{ summary.total }}</li>
                    <li>Passed: <span class="pass">{{ summary.success }}</span></li>
                    <li>Failed: <span class="fail">{{ summary.failure }}</span></li>
                    <li>Success Rate: {{ summary.success_percentage }}%</li>
                </ul>
            </div>

            <div class="d-flex justify-content-between align-items-center mb-3">
                <h3>Detailed Results</h3>
            </div>

            <table id="resultsTable" class="table table-striped">
                <thead>
                    <tr>
                        <th>Conversation</th>
                        <th>Expected Target</th>
                        <th>Actual Target</th>
                        <th>Confidence</th>
                        <th>Reasoning</th>
                        <th>Status</th>
                    </tr>
                </thead>
                <tbody>
                    {% for result in test_results %}
                    <tr>
                        <td><pre>{{ result.conversation }}</pre></td>
                        <td>{{ result.expected_target }}</td>
                        <td>{{ result.actual_target }}</td>
                        <td>{{ result.confidence }}</td>
                        <td>{{ result.reasoning }}</td>
                        <td>
                            {% if result.status == "PASS" %}
                                <span class="pass">{{ result.status }}</span>
                            {% else %}
                                <span class="fail">{{ result.status }}</span>
                            {% endif %}
                        </td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>

        <script src="https://code.jquery.com/jquery-3.6.0.min.js"></script>
        <script src="https://cdn.datatables.net/1.13.4/js/jquery.dataTables.min.js"></script>
        <script src="https://cdn.datatables.net/1.13.4/js/dataTables.bootstrap5.min.js"></script>
        <script>
            $(document).ready(function() {
                var table = $('#resultsTable').DataTable({
                    "order": [[ 0, "asc" ]],
                    "pageLength": 10
                });
            });
        </script>
    </body>
    </html>
    """

    template = env.from_string(template_str)

    # Render the template with context
    html_content = template.render(
        current_date=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        test_results=test_results,
        summary=summary,
        report_name=report_name
    )

    # Define the filename
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    filename = f"{timestamp}-{report_name}.html"
    filepath = os.path.join(abs_output_dir, filename)

    # Save the HTML content to the file
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(html_content)

    return filepath
