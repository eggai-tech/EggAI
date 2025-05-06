import asyncio
import random
from time import perf_counter
from typing import Any, Dict, List
from uuid import uuid4

import dspy
import pytest
from dotenv import load_dotenv

from eggai import Agent, Channel
from agents.triage.config import Settings
from libraries.dspy_set_language_model import dspy_set_language_model
from ..agent import triage_agent
from ..data_sets.loader import load_dataset_triage_testing, translate_agent_str_to_enum
from ..models import AGENT_REGISTRY, TargetAgent

# ---------------------------------------------------------------------------
# Global setup
# ---------------------------------------------------------------------------

settings = Settings()
load_dotenv()
dspy_set_language_model(settings)


class TriageEvaluationSignature(dspy.Signature):
    """DSPy program signature for judging the triage routing decision."""

    chat_history: str = dspy.InputField(desc="Full conversation context.")
    agent_response: TargetAgent = dspy.InputField(desc="Agent selected by triage.")
    expected_target_agent: TargetAgent = dspy.InputField(desc="Ground‑truth agent label.")

    judgment: bool = dspy.OutputField(desc="Pass (True) or Fail (False).")
    reasoning: str = dspy.OutputField(desc="Detailed justification in Markdown.")
    precision_score: float = dspy.OutputField(desc="Precision score (0.0–1.0).")


# ---------------------------------------------------------------------------
# Test infrastructure
# ---------------------------------------------------------------------------

test_agent = Agent("TestTriageAgent")

test_channel = Channel("human")
agents_channel = Channel("agents")

# A central queue that gathers every non‑user event we receive from triage
_response_queue: asyncio.Queue[Dict[str, Any]] = asyncio.Queue()


@test_agent.subscribe(
    channel=agents_channel,
    filter_by_message=lambda event: event.get("type") != "user_message",
)
async def _handle_response(event):
    """Push every triage event into the asyncio queue so the pytest coroutine can consume it."""
    await _response_queue.put(event)


# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------

def _markdown_table(rows: List[List[str]], headers: List[str]) -> str:
    """Return a GitHub‑style markdown table given *headers* and *rows*."""
    # Calculate max width per column
    widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(cell))

    def _fmt_row(cells):
        return "| " + " | ".join(cell.ljust(widths[i]) for i, cell in enumerate(cells)) + " |"

    sep = "| " + " | ".join("-" * widths[i] for i in range(len(headers))) + " |"
    out = [_fmt_row(headers), sep]
    out.extend(_fmt_row(r) for r in rows)
    return "\n".join(out)

@pytest.mark.asyncio
async def test_triage_agent():
    """Send all test conversations concurrently, collect rich metrics, and log a results table."""

    await triage_agent.start()
    await test_agent.start()

    random.seed(42)
    test_dataset = random.sample(load_dataset_triage_testing(), 10)

    # Map message_id → dataset case plus start timestamp
    pending: Dict[str, Any] = {}

    # Storage for per‑case results
    results: List[Dict[str, Any]] = []

    # -------------------------------------------------------------------
    # 1. Fire off *all* user messages without awaiting individual responses
    # -------------------------------------------------------------------

    for dataset_case in test_dataset:
        message_id = str(uuid4())
        pending[message_id] = dataset_case

        await test_channel.publish(
            {
                "id": message_id,  # propagate msg id to top‑level id for easier tracking
                "type": "user_message",
                "source": "TestTriageAgent",
                "data": {
                    "chat_messages": [
                        {"role": "User", "content": dataset_case.conversation},
                    ],
                    "connection_id": str(uuid4()),
                    "message_id": message_id,
                },
            }
        )

    # -------------------------------------------------------------------
    # 2. Consume responses from the queue and evaluate routing decisions
    # -------------------------------------------------------------------

    errors: List[str] = []

    async def _process_event(event: Dict[str, Any]):
        """Evaluate a single triage response event and store metrics."""
        message_id = event.get("data", {}).get("message_id")
        latency = event.get("data", {}).get("latency", 0.0)
        if not message_id or message_id not in pending:
            return  # Unknown or duplicate event – ignore

        case = pending.pop(message_id)
        latency_ms = latency * 1000.0

        routed_agent = next(
            (
                key
                for key, value in AGENT_REGISTRY.items()
                if value["message_type"] == event["type"]
            ),
            "UnknownAgent",
        )

        # Ask DSPy to judge the decision
        eval_model = dspy.asyncify(dspy.Predict(TriageEvaluationSignature))
        evaluation = await eval_model(
            chat_history=case.conversation,
            agent_response=routed_agent,
            expected_target_agent=case.target_agent,
        )

        # Save granular metrics for later reporting
        results.append(
            {
                "id": message_id[:8],
                "expected": translate_agent_str_to_enum(case.target_agent),
                "routed": routed_agent,
                "judgment": "✔" if evaluation.judgment else "✘",
                "precision": f"{evaluation.precision_score:.2f}",
                "latency": f"{latency_ms:.1f} ms",
                "reason": (evaluation.reasoning or "")[:40] + ("…" if len(evaluation.reasoning or "") > 40 else ""),
            }
        )

        # Collect any deviations for final assertion
        if routed_agent != case.target_agent:
            errors.append(
                (
                    "Expected agent '{expected}', but triage routed to '{actual}'. "
                    "Conversation start: '{snippet}…'"
                ).format(
                    expected=translate_agent_str_to_enum(case.target_agent),
                    actual=routed_agent,
                    snippet=case.conversation[:60].replace("\n", " "),
                )
            )

        if not evaluation.judgment:
            errors.append(f"DSPy judged routing incorrect: {evaluation.reasoning}")

        if not 0.8 <= evaluation.precision_score <= 1.0:
            errors.append(
                f"Precision score {evaluation.precision_score:.2f} outside acceptable range [0.8, 1.0]."
            )

    timeout_per_msg = 30.0
    try:
        while pending:
            event = await asyncio.wait_for(_response_queue.get(), timeout=timeout_per_msg)
            await _process_event(event)
    except asyncio.TimeoutError:
        for mid, dataset_case in pending.items():
            errors.append(
                (
                    f"Timeout (> {timeout_per_msg}s): no triage response for message_id {mid}. "
                    f"Conversation start: '{dataset_case.conversation[:60].replace('\n', ' ')}…'"
                )
            )

    # -------------------------------------------------------------------
    # 3. Log detailed results as a markdown table
    # -------------------------------------------------------------------

    headers = [
        "ID",
        "Expected",
        "Routed",
        "PASS/FAIL",
        "Latency",
        "LLM ✓",
        "LLM Prec",
        "LLM Reason (trunc)",
    ]
    rows = [
        [
            r["id"],
            r["expected"],
            r["routed"],
            "✓" if r["expected"] == r["routed"] else "✘",
            r["latency"],
            r["judgment"],
            r["precision"],
            r["reason"],
        ]
        for r in results
    ]
    table_str = _markdown_table(rows, headers)

    print("\n=== Triage test results ===\n")
    print(table_str)
    print("\n===========================\n")

    # -------------------------------------------------------------------
    # 4. Final assertion block
    # -------------------------------------------------------------------

    if errors:
        pytest.fail("\n\n".join(errors))
