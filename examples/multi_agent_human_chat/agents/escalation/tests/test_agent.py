import asyncio
import pytest
import dspy
from uuid import uuid4
from eggai import Agent, Channel
from ..agent import escalation_agent

dspy.configure(lm=dspy.LM("openai/gpt-4o-mini"))

test_cases = [
    {
        "chat_messages": [
            {
                "role": "User",
                "content": "My issue wasn't resolved by PoliciesAgent. I'm still having trouble.",
            },
            {
                "role": "EscalationAgent",
                "content": "Certainly. Could you describe the issue in more detail?",
            },
            {
                "role": "User",
                "content": "It's about my billing setup. The website keeps throwing an error.",
            },
        ],
        "expected_meaning": (
            "The agent should ensure the user confirms before proceeding with ticket creation. "
            "It should acknowledge the issue and explicitly ask for confirmation in a way that the user understands."
        ),
    }
]


class EscalationEvaluationSignature(dspy.Signature):
    chat_history: str = dspy.InputField(desc="Full conversation context.")
    agent_response: str = dspy.InputField(desc="Agent-generated response.")
    expected_meaning: str = dspy.InputField(desc="Expected meaning of the response.")

    judgment: bool = dspy.OutputField(desc="Pass (True) or Fail (False).")
    reasoning: str = dspy.OutputField(desc="Detailed justification in Markdown.")
    precision_score: float = dspy.OutputField(desc="Precision score (0.0 to 1.0).")


test_agent = Agent("TestEscalationAgent")
test_channel = Channel("agents")
human_channel = Channel("human")

event_received = asyncio.Event()
received_event = None


@test_agent.subscribe(
    channel=human_channel, filter_func=lambda event: event["type"] == "agent_message",
)
async def handle_response(event):
    print(f"Received event: {event}")
    global received_event
    received_event = event
    event_received.set()


@pytest.mark.asyncio
async def test_escalation_agent():
    await escalation_agent.start()
    await test_agent.start()

    for case in test_cases:
        event_received.clear()

        await test_channel.publish(
            {
                "id": str(uuid4()),
                "type": "escalation_request",
                "meta": {},
                "payload": {"chat_messages": case["chat_messages"]},
            }
        )

        try:
            await asyncio.wait_for(event_received.wait(), timeout=5.0)
        except asyncio.TimeoutError:
            pytest.fail("Timeout: No response event received for chat history.")

        assert received_event is not None, "No agent response received."
        assert received_event["type"] == "agent_message", (
            "Unexpected event type received."
        )
        assert isinstance(received_event["payload"], str), "Payload should be a string."

        agent_response = received_event["payload"]

        eval_model = dspy.asyncify(dspy.Predict(EscalationEvaluationSignature))
        evaluation_result = await eval_model(
            chat_history="\n".join(
                [f"{m['role']}: {m['content']}" for m in case["chat_messages"]]
            ),
            agent_response=agent_response,
            expected_meaning=case["expected_meaning"],
        )

        assert evaluation_result.judgment, (
            "Judgment must be True. " + evaluation_result.reasoning
        )

        assert 0.7 <= evaluation_result.precision_score <= 1.0, (
            "Precision score must be between 0.7 and 1.0."
        )
