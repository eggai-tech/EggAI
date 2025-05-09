import asyncio
import random
import os
from typing import Any, Dict, List
from uuid import uuid4
from datetime import datetime

import dspy
import pytest
from dotenv import load_dotenv
from jinja2 import Environment, FileSystemLoader, select_autoescape

from eggai import Agent, Channel
from agents.triage.config import Settings
from libraries.dspy_set_language_model import dspy_set_language_model
from libraries.logger import get_console_logger
from ..agent import triage_agent
from ..data_sets.loader import load_dataset_triage_testing, translate_agent_str_to_enum
from ..models import AGENT_REGISTRY, TargetAgent
from agents.triage.agent import handle_user_message
from libraries.tracing import TracedMessage
from unittest.mock import AsyncMock

# ---------------------------------------------------------------------------
# Global setup
# ---------------------------------------------------------------------------
load_dotenv()
settings = Settings()
logger = get_console_logger("triage_test")
dspy_set_language_model(settings)


# ---------------------------------------------------------------------------
# Utility for formatting console tables
# ---------------------------------------------------------------------------
def _markdown_table(rows: List[List[str]], headers: List[str]) -> str:
    widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(cell))

    def _fmt_row(cells):
        return "| " + " | ".join(cell.ljust(widths[i]) for i, cell in enumerate(cells)) + " |"

    sep = "| " + " | ".join("-" * widths[i] for i in range(len(headers))) + " |"
    lines = [_fmt_row(headers), sep] + [_fmt_row(r) for r in rows]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# DSPy signature for LLM judging
# ---------------------------------------------------------------------------
class TriageEvaluationSignature(dspy.Signature):
    chat_history: str = dspy.InputField(desc="Full conversation context.")
    agent_response: TargetAgent = dspy.InputField(desc="Agent selected by triage.")
    expected_target_agent: TargetAgent = dspy.InputField(desc="Ground-truth agent label.")

    judgment: bool = dspy.OutputField(desc="Pass (True) or Fail (False).")
    reasoning: str = dspy.OutputField(desc="Detailed justification in Markdown.")
    precision_score: float = dspy.OutputField(desc="Precision score (0.0–1.0).")


# ---------------------------------------------------------------------------
# Report generation functions (embedded)
# ---------------------------------------------------------------------------
def write_html_report(test_results: List[Dict[str, Any]], summary: Dict[str, Any], report_name: str) -> str:
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
            body { padding: 20px; }
            .summary { margin-bottom: 30px; }
            .pass { color: green; font-weight: bold; }
            .fail { color: red; font-weight: bold; }
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
            <h3>Detailed Results</h3>
            <table id="resultsTable" class="table table-striped">
                <thead>
                    <tr>
                        <th>Conversation</th>
                        <th>Expected</th>
                        <th>Routed</th>
                        <th>Latency (ms)</th>
                        <th>Status</th>
                        <th>LLM ✓</th>
                        <th>LLM Prec</th>
                        <th >Reasoning</th>
                    </tr>
                </thead>
                <tbody>
                    {% for r in test_results %}
                    <tr>
                        <td><pre>{{ r.conversation }}</pre></td>
                        <td>{{ r.expected_target }}</td>
                        <td>{{ r.actual_target }}</td>
                        <td>{{ r.latency_value }}</td>
                        <td>{% if r.status == 'PASS' %}<span class="pass">{{ r.status }}</span>{% else %}<span class="fail">{{ r.status }}</span>{% endif %}</td>
                        <td>{{ r.llm_judgment }}</td>
                        <td>{{ r.llm_precision }}</td>
                        <td><pre>{{ r.llm_reasoning }}</pre></td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
        <script src="https://code.jquery.com/jquery-3.6.0.min.js"></script>
        <script src="https://cdn.datatables.net/1.13.4/js/jquery.dataTables.min.js"></script>
        <script src="https://cdn.datatables.net/1.13.4/js/dataTables.bootstrap5.min.js"></script>
        <script>
            $(document).ready(function() { $('#resultsTable').DataTable({ "order": [[ 0, "asc" ]], "pageLength": 10 }); });
        </script>
    </body>
    </html>
    """

    template = env.from_string(template_str)
    html_content = template.render(
        current_date=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        test_results=test_results,
        summary=summary,
        report_name=report_name
    )

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    filename = f"{timestamp}-{report_name}.html"
    filepath = os.path.join(abs_output_dir, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(html_content)
    return filepath


# ---------------------------------------------------------------------------
# Test infrastructure
# ---------------------------------------------------------------------------

test_agent = Agent("TestTriageAgent")
test_channel = Channel("human")
agents_channel = Channel("agents")

_response_queue: asyncio.Queue[TracedMessage] = asyncio.Queue()


@test_agent.subscribe(
    channel=agents_channel,
    filter_by_message=lambda event: event.get("type") != "user_message",
    auto_offset_reset="latest",
    group_id="test_agent_group-agents"
)
async def _handle_response(event: TracedMessage):
    await _response_queue.put(event)


@test_agent.subscribe(
    channel=test_channel,
    filter_by_message=lambda event: event.get("type") == "agent_message",
    auto_offset_reset="latest",
    group_id="test_agent_group-human"
)
async def _handle_test_message(event: TracedMessage):
    await _response_queue.put(event)


# ---------------------------------------------------------------------------
# Main refactored test with report integration
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_triage_agent():
    """Send all test conversations, validate classifier, then use LLM judge with controlled concurrency, then generate report."""

    # Start agents
    await triage_agent.start()
    await test_agent.start()

    # Phase 1: Send test cases
    random.seed(1989)
    test_dataset = random.sample(load_dataset_triage_testing(), 10)
    pending: Dict[str, Any] = {}
    classification_results: List[Dict[str, Any]] = []

    for case in test_dataset:
        msg_id = str(uuid4())
        pending[msg_id] = case
        await test_channel.publish({
            "id": msg_id,
            "type": "user_message",
            "source": "TestTriageAgent",
            "data": {
                "chat_messages": [{"role": "User", "content": case.conversation}],
                "connection_id": str(uuid4()),
                "message_id": msg_id
            },
        })

    # Phase 2: Collect classifications
    classification_errors: List[str] = []
    for _ in range(len(test_dataset)):
        event = await _response_queue.get()
        mid = event.data.get("message_id")
        if mid not in pending:
            logger.warning(f"Unexpected message ID: {mid}")
            continue
        case = pending.pop(mid)
        latency_ms = event.data.get("metrics").get("latency_ms")
        routed = next(
            (k for k, v in AGENT_REGISTRY.items() if v.get("message_type", "agent_message") == event.type),
            "UnknownAgent"
        )
        if routed == "UnknownAgent" and event["type"] == "agent_message":
            routed = "ChattyAgent"
        classification_results.append({
            "id": mid,
            "expected": translate_agent_str_to_enum(case.target_agent),
            "routed": routed,
            "latency": f"{latency_ms:.1f} ms",
            "latency_value": f"{latency_ms:.1f}",
            "conversation": case.conversation,
            "expected_target_agent": case.target_agent
        })
        if routed != translate_agent_str_to_enum(case.target_agent):
            classification_errors.append(
                f"Expected {translate_agent_str_to_enum(case.target_agent)}, got {routed} (ID {mid[:8]})")

    # Phase 3: LLM judging
    eval_fn = dspy.asyncify(dspy.Predict(TriageEvaluationSignature))
    semaphore = asyncio.Semaphore(10)

    async def limited_eval(res):
        async with semaphore:
            ev = await eval_fn(
                chat_history=res['conversation'],
                agent_response=res['routed'],
                expected_target_agent=res['expected_target_agent']
            )
            return res, ev

    tasks = [asyncio.create_task(limited_eval(r)) for r in classification_results]
    judge_results: List[Dict[str, Any]] = []
    for coro in asyncio.as_completed(tasks):
        res, ev = await coro
        passed = ev.judgment
        prec = ev.precision_score
        reason = ev.reasoning or ""
        print(f"ID {res['id']}: judgment={passed}, precision={prec:.2f}, reason={reason[:40]}...")
        judge_results.append({
            **res,
            "judgment": "✔" if passed else "✘",
            "precision": f"{prec:.2f}",
            "reason": reason
        })

    # Phase 4: Console report
    headers = ["ID", "Expected", "Routed", "Latency", "LLM ✓", "LLM Prec", "Reason"]
    rows = [[r['id'], r['expected'], r['routed'], r['latency'], r['judgment'], r['precision'], r['reason'][:20]] for r
            in judge_results]
    print("\n=== Results ===\n")
    print(_markdown_table(rows, headers))

    # Phase 5: HTML report
    report_data = []
    for r in judge_results:
        report_data.append({
            "conversation": r["conversation"],
            "expected_target": r["expected"],
            "actual_target": r["routed"],
            "latency_value": r["latency_value"],
            "status": "PASS" if r["judgment"] == "✔" else "FAIL",
            "llm_judgment": r["judgment"],
            "llm_precision": r["precision"],
            "llm_reasoning": r["reason"]
        })
    summary = {
        "total": len(report_data),
        "success": sum(1 for r in report_data if r["status"] == "PASS"),
        "failure": sum(1 for r in report_data if r["status"] == "FAIL"),
        "success_percentage": f"{sum(1 for r in report_data if r['status'] == 'PASS') / len(report_data) * 100:.2f}"
    }

    report_path = write_html_report(report_data, summary, "classifier_" + settings.classifier_version)
    print(f"HTML report generated at: file://{report_path}")


# ---------------------------------------------------------------------------
# Simple unit tests
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_triage_agent_simple(monkeypatch):
    load_dotenv()
    test_message = TracedMessage(
        id=str(uuid4()),
        type="user_message",
        source="TestTriageAgent",
        data={
            "chat_messages": [{"role": "user", "content": "hi how are you?"}],
            "connection_id": str(uuid4()),
            "agent": "TriageAgent"
        }
    )
    mock_publish = AsyncMock()
    monkeypatch.setattr(Channel, "publish", mock_publish)
    await handle_user_message(test_message)
    args, _ = mock_publish.call_args_list[0]
    assert args[0].data.get("agent") == "TriageAgent"


@pytest.mark.asyncio
async def test_triage_agent_intent_change(monkeypatch):
    load_dotenv()
    test_message = TracedMessage(
        id=str(uuid4()),
        type="user_message",
        source="TestTriageAgent",
        data={
            "chat_messages": [
                {"role": "user", "content": "hi how are you?"},
                {"role": "assistant", "agent": "ChattyAgent", "content": "Hey, I'm good! How can I help you?"},
                {"role": "user", "content": "could you please give me my policy details?"},
            ],
            "connection_id": str(uuid4()),
            "agent": "TriageAgent"
        }
    )
    mock_publish = AsyncMock()
    monkeypatch.setattr(Channel, "publish", mock_publish)
    await handle_user_message(test_message)
    args, _ = mock_publish.call_args_list[0]
    assert args[0].type == "policy_request"
