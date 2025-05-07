import asyncio
import random
from typing import Any, Dict, List
from uuid import uuid4

import dspy
import pytest
from dotenv import load_dotenv

from eggai import Agent, Channel
from agents.triage.config import Settings
from libraries.dspy_set_language_model import dspy_set_language_model
from libraries.logger import get_console_logger
from ..agent import triage_agent
from ..data_sets.loader import load_dataset_triage_testing, translate_agent_str_to_enum
from ..models import AGENT_REGISTRY, TargetAgent
from unittest.mock import AsyncMock
from agents.triage.agent import handle_user_message
from libraries.tracing import TracedMessage

# ---------------------------------------------------------------------------
# Global setup
# ---------------------------------------------------------------------------
load_dotenv()
settings = Settings()
logger = get_console_logger("triage_test")
dspy_set_language_model(settings)


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
# Utilities
# ---------------------------------------------------------------------------

def _markdown_table(rows: List[List[str]], headers: List[str]) -> str:
    widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(cell))

    def _fmt_row(cells):
        return "| " + " | ".join(cell.ljust(widths[i]) for i, cell in enumerate(cells)) + " |"

    sep = "| " + " | ".join("-" * widths[i] for i in range(len(headers))) + " |"
    lines = [_fmt_row(headers), sep]
    lines += [_fmt_row(r) for r in rows]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main refactored test
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_triage_agent():
    """Send all test conversations, validate classifier, then use LLM judge with controlled concurrency."""

    # Start agents
    await triage_agent.start()
    await test_agent.start()

    # Sample test cases
    random.seed(1989)
    test_dataset = random.sample(load_dataset_triage_testing(), 10)

    # Phase 1: Fire off all messages
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
                "message_id": msg_id,
            },
        })

    # Phase 2: Collect classification decisions
    classification_errors: List[str] = []
    for _ in range(len(test_dataset)):
        event = await _response_queue.get()
        mid = event.data.get("message_id")

        if mid not in pending:
            logger.warning(f"Received unexpected message ID: {mid}")
            logger.warning(pending)
            continue
        case = pending.pop(mid)
        latency = event.data.get("metrics").get("latency_ms")

        routed = next(
            (k for k, v in AGENT_REGISTRY.items() if v.get("message_type", "agent_message") == event.type),
            "UnknownAgent",
        )
        if routed == "UnknownAgent":
            if event["type"] == "agent_message":
                routed = "ChattyAgent"

        classification_results.append({
            "id": mid,
            "expected": translate_agent_str_to_enum(case.target_agent),
            "routed": routed,
            "latency": f"{latency:.1f} ms",
            "conversation": case.conversation,
            "expected_target_agent": case.target_agent,
        })

        if routed != translate_agent_str_to_enum(case.target_agent):
            classification_errors.append(
                f"Expected '{translate_agent_str_to_enum(case.target_agent)}', but got '{routed}' (ID {mid[:8]})."
            )

    # Phase 3: LLM judge with controlled concurrency
    eval_fn = dspy.asyncify(dspy.Predict(TriageEvaluationSignature))
    semaphore = asyncio.Semaphore(10)

    async def limited_eval(res: Dict[str, Any]) -> Any:
        async with semaphore:
            evaluation = await eval_fn(
                chat_history=res['conversation'],
                agent_response=res['routed'],
                expected_target_agent=res['expected_target_agent'],
            )
            return res, evaluation

    tasks = [asyncio.create_task(limited_eval(res)) for res in classification_results]

    judge_results: List[Dict[str, Any]] = []
    for coro in asyncio.as_completed(tasks):
        res, evaluation = await coro
        passed = evaluation.judgment
        prec = evaluation.precision_score
        reason = evaluation.reasoning or ""

        print(
            f"ID {res['id']}: judgment={passed}, precision={prec:.2f}, reason={reason[:40]}{'...' if len(reason) > 40 else ''}"
        )

        judge_results.append({
            **res,
            "judgment": "✔" if passed else "✘",
            "precision": f"{prec:.2f}",
            "reason": reason[:40] + ("..." if len(reason) > 40 else ""),
        })

    # Phase 4: Report full results
    headers = [
        "ID", "Expected", "Routed", "Latency", "LLM ✓", "LLM Prec", "LLM Reason (trunc)"
    ]
    rows = [
        [
            r["id"], r["expected"], r["routed"], r["latency"],
            r["judgment"], r["precision"], r["reason"],
        ]
        for r in judge_results
    ]
    table = _markdown_table(rows, headers)

    print("\n=== Triage test results ===\n")
    print(table)
    print("\n===========================\n")

    # Phase 5: Final assertions
    final_errors: List[str] = []
    final_errors.extend(classification_errors)
    for r in judge_results:
        if r["routed"] != r["expected"]:
            final_errors.append(
                f"Routing mismatch: expected {r['expected']} but got {r['routed']} (ID {r['id']})"
            )
        if r["judgment"] != "✔":
            final_errors.append(f"LLM judged routing incorrect for ID {r['id']}")
        if not (0.8 <= float(r["precision"]) <= 1.0):
            final_errors.append(
                f"Precision {float(r['precision']):.2f} out of range [0.8,1.0] for ID {r['id']}"
            )
    if final_errors:
        pytest.fail("\n".join(final_errors))


# ---------------------------------------------------------------------------
# Simple unit tests unchanged
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_triage_agent_simple(monkeypatch):
    load_dotenv()
    test_message = TracedMessage(
        id=str(uuid4()),
        type="user_message",
        source="frontend_agent",
        data={
            "chat_messages": [{"role": "User", "content": "hi how are you?"}],
            "connection_id": str(uuid4()),
            "agent": "TriageAgent",
        },
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
        source="frontend_agent",
        data={
            "chat_messages": [
                {"role": "User", "content": "hi how are you?"},
                {
                    "role": "assistant",
                    "agent": "ChattyAgent",
                    "content": (
                        "I'm here to help you with your insurance needs! ..."
                    ),
                },
                {"role": "User", "content": "could you please give me my policy details?"},
            ],
            "connection_id": str(uuid4()),
            "agent": "TriageAgent",
        },
    )
    mock_publish = AsyncMock()
    monkeypatch.setattr(Channel, "publish", mock_publish)
    await handle_user_message(test_message)

    args, _ = mock_publish.call_args_list[0]
    assert args[0].type == "policy_request"
