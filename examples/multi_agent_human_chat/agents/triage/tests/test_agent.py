import asyncio
import pytest
import dspy
from uuid import uuid4
from eggai import Agent, Channel
from ..agent import triage_agent
from ..config import settings
from dotenv import load_dotenv

from agents.triage.config import Settings
settings = Settings()

load_dotenv()
dspy.configure(lm=dspy.configure(lm=dspy.LM("openai/gpt-4o-mini")))

# Test data for the TriageAgent
test_cases = [
    {
        "chat_history": "User: I need help with my billing issue.",
        "expected_target_agent": "BillingAgent",
    },
    {
        "chat_history": "User: My policy details seem incorrect.",
        "expected_target_agent": "PoliciesAgent",
    },
]


class TriageEvaluationSignature(dspy.Signature):
    chat_history: str = dspy.InputField(desc="Full conversation context.")
    agent_response: str = dspy.InputField(desc="Agent-generated response.")
    expected_target_agent: str = dspy.InputField(desc="Expected agent classification.")

    judgment: bool = dspy.OutputField(desc="Pass (True) or Fail (False).")
    reasoning: str = dspy.OutputField(desc="Detailed justification in Markdown.")
    precision_score: float = dspy.OutputField(desc="Precision score (0.0 to 1.0).")


# Set up test agent and channels
test_agent = Agent("TestTriageAgent")
test_channel = Channel("human")
agents_channel = Channel("agents")

event_received = asyncio.Event()
received_event = None


@test_agent.subscribe(
    channel=agents_channel,
    filter_by_message=lambda event: event.get("type")
    in ["billing_request", "policy_request"],
)
async def handle_response(event):
    global received_event
    received_event = event
    event_received.set()


@pytest.mark.asyncio
async def test_triage_agent():
    await triage_agent.start()
    await test_agent.start()

    for case in test_cases:
        event_received.clear()

        # Simulate a user message event
        await test_channel.publish(
            {
                "id": str(uuid4()),
                "type": "user_message",
                "source": "TestTriageAgent",
                "data": {
                    "chat_messages": [
                        {"role": "User", "content": case["chat_history"]},
                    ],
                    "connection_id": str(uuid4()),
                    "message_id": str(uuid4()),
                },
            }
        )

        try:
            await asyncio.wait_for(event_received.wait(), timeout=5.0)
        except asyncio.TimeoutError:
            pytest.fail(
                f"Timeout: No response event received for chat history: {case['chat_history']}"
            )

        assert received_event is not None, "No agent response received."

        agent_type = next(
            (
                key
                for key, value in settings.agent_registry.items()
                if value["message_type"] == received_event["type"]
            ),
            "UnknownAgent",
        )

        assert agent_type == case["expected_target_agent"], (
            f"Expected agent '{case['expected_target_agent']}', but triage routed to '{agent_type}'."
        )

        # Evaluate the response
        eval_model = dspy.asyncify(dspy.Predict(TriageEvaluationSignature))
        evaluation_result = await eval_model(
            chat_history=case["chat_history"],
            agent_response=agent_type,
            expected_target_agent=case["expected_target_agent"],
        )

        assert evaluation_result.judgment, (
            "Judgment must be True. " + evaluation_result.reasoning
        )
        assert 0.8 <= evaluation_result.precision_score <= 1.0, (
            "Precision score must be between 0.8 and 1.0."
        )
