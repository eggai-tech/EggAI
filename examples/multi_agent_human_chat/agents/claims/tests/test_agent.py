import asyncio
import pytest
import dspy
from uuid import uuid4
from eggai import Agent, Channel
from ..agent import claims_agent
from libraries.tracing import TracedMessage
from libraries.logger import get_console_logger

logger = get_console_logger("claims_agent.tests")

dspy.configure(lm=dspy.LM("openai/gpt-4o-mini"))

test_cases = [
    {
        "chat_history": (
            "User: Hi, I'd like to check my claim status.\n"
            "ClaimsAgent: Sure! Could you please provide your claim number?\n"
            "User: It's 1001.\n"
        ),
        "expected_response": (
            "Your claim #1001 is currently 'In Review'. "
            "We estimate a payout of $2300.00 by 2025-05-15. "
            "We’re still awaiting your repair estimates—please submit them at your earliest convenience."
        ),
    }
]

class ClaimsEvaluationSignature(dspy.Signature):
    chat_history: str = dspy.InputField(desc="Full conversation context.")
    agent_response: str = dspy.InputField(desc="Agent-generated response.")
    expected_response: str = dspy.InputField(desc="Expected correct response.")

    judgment: bool = dspy.OutputField(desc="Pass (True) or Fail (False).")
    reasoning: str = dspy.OutputField(desc="Detailed justification in Markdown.")
    precision_score: float = dspy.OutputField(desc="Precision score (0.0 to 1.0).")

# Set up test agents and channels
test_agent = Agent("TestClaimsAgent")
test_channel = Channel("agents")
human_channel = Channel("human")

event_received = asyncio.Event()
received_event = None

@test_agent.subscribe(
    channel=human_channel,
    filter_by_message=lambda event: event.get("type") == "agent_message",
)
async def handle_response(event):
    logger.info(f"Received event: {event}")
    global received_event
    received_event = event
    event_received.set()

@pytest.mark.asyncio
async def test_claims_agent():
    await claims_agent.start()
    await test_agent.start()

    for case in test_cases:
        event_received.clear()

        # Simulate a claims request event
        await test_channel.publish(
            TracedMessage(
                id=str(uuid4()),
                type="claims_request",
                source="TestClaimsAgent",
                data={
                    "chat_messages": [
                        {"role": "User", "content": "Hi, I'd like to check my claim status."},
                        {"role": "ClaimsAgent", "content": "Sure! Could you please provide your claim number?"},
                        {"role": "User", "content": "It's 1001."},
                    ]
                },
            )
        )

        try:
            await asyncio.wait_for(event_received.wait(), timeout=5.0)
        except asyncio.TimeoutError:
            pytest.fail(
                f"Timeout: No response event received for chat history: {case['chat_history']}"
            )

        assert received_event is not None, "No agent response received."
        assert received_event["type"] == "agent_message", (
            "Unexpected event type received."
        )
        assert isinstance(received_event["data"]["message"], str), "Message should be a string."

        agent_response = received_event["data"]["message"]

        # Evaluate the response
        eval_model = dspy.asyncify(dspy.Predict(ClaimsEvaluationSignature))
        evaluation_result = await eval_model(
            chat_history=case["chat_history"],
            agent_response=agent_response,
            expected_response=case["expected_response"],
        )

        assert evaluation_result.judgment, (
            "Judgment must be True. " + evaluation_result.reasoning
        )
        assert 0.8 <= evaluation_result.precision_score <= 1.0, (
            "Precision score must be between 0.8 and 1.0."
        )
