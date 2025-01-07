import json
import os
import random
from unittest.mock import AsyncMock
from datetime import datetime
from jinja2 import Environment, FileSystemLoader, select_autoescape
import pytest
from dotenv import load_dotenv

from eggai import Channel
from examples.example_08_dspy.src.triage import handle_user_message, AGENT_REGISTRY


def parse_conversation(conversation):
    messages = []
    lines = conversation.strip().split("\n")
    for line in lines:
        if line.startswith("User:"):
            content = line[len("User:") :].strip()
            messages.append({"role": "user", "content": content})
        else:
            try:
                agent_name, content = line.split(":", 1)
                agent_name = agent_name.strip()
                content = content.strip()
                messages.append(
                    {"role": "assistant", "content": content, "agent": agent_name}
                )
            except ValueError:
                continue
    return messages


@pytest.mark.asyncio
async def test_not_optimized_agent(monkeypatch):
    load_dotenv()

    dataset_path = os.path.join(
        os.path.dirname(__file__), "..", "datasets", "triage-training.json"
    )
    with open(dataset_path, "r") as f:
        dataset = json.load(f)

    total = len(dataset)
    success = 0
    failure = 0
    test_results = []

    for entry in dataset:
        conversation = entry["conversation"]
        expected_target = entry["target"]
        test_id = entry.get("id", "N/A")

        chat_messages = parse_conversation(conversation)

        test_event = {
            "type": "user_message",
            "payload": {"chat_messages": chat_messages},
        }

        mock_publish = AsyncMock()
        monkeypatch.setattr(Channel, "publish", mock_publish)
        await handle_user_message(test_event)

        args, kwargs = mock_publish.call_args_list[0]
        message_type = args[0].get("type", "agent_message")
        meta = args[0].get("meta")
        confidence = meta["confidence"]
        reasoning = meta["reasoning"]

        if message_type == "agent_message":
            actual_target = "TriageAgent"
        else:
            actual_target = [
                key
                for key, value in AGENT_REGISTRY.items()
                if value["message_type"] == message_type
            ][0]

        if actual_target == expected_target:
            status = "PASS"
            success += 1
            print(f"Test Case #{test_id}: PASS")
        else:
            status = "FAIL"
            failure += 1
            print(
                f"Test Case #{test_id}: FAIL (Expected: {expected_target}, Got: {actual_target})"
            )

        test_results.append(
            {
                "test_id": test_id,
                "conversation": conversation,
                "expected_target": expected_target,
                "actual_target": actual_target,
                "status": status,
                "confidence": confidence,
                "reasoning": reasoning,
            }
        )

    success_percentage = (success / total) * 100
    print(
        f"\nTotal: {total}, Success: {success}, Failure: {failure}, Success Rate: {success_percentage:.2f}%"
    )

    # Prepare summary for the report
    summary = {
        "total": total,
        "success": success,
        "failure": failure,
        "success_percentage": f"{success_percentage:.2f}",
    }

    # Generate the HTML report
    generate_html_report(test_results, summary)

    # Assert if success percentage is greater than 50%
    assert (
        success_percentage > 50
    ), f"Success rate {success_percentage:.2f}% is not greater than 50%."


def generate_html_report(test_results, summary, output_dir="reports"):
    os.makedirs(output_dir, exist_ok=True)

    # Define the HTML template
    env = Environment(
        loader=FileSystemLoader(searchpath="./"),
        autoescape=select_autoescape(["html", "xml"]),
    )

    # HTML Template with Bootstrap and DataTables for styling and interactivity
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
        <div class="container">
            <h1 class="mb-4">EggAI - Performance Report - Triage Agent</h1>
            <p><strong>Date:</strong> {{ current_date }}</p>

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
                        <th>Test ID</th>
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
                        <td>{{ result.test_id }}</td>
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
    )

    # Define the filename
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    filename = f"{timestamp}-triage-agent-report.html"
    filepath = os.path.join(output_dir, filename)

    # Save the HTML content to the file
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(html_content)

    print(f"Report generated and saved to {filepath}")
