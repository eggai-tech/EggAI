import asyncio
import pytest
import dspy
from uuid import uuid4
from eggai import Agent, Channel
from ..agent import billing_agent
from libraries.logger import get_console_logger

logger = get_console_logger("billing_agent.tests")

dspy.configure(lm=dspy.LM("openai/gpt-4o-mini"))

# Sample test data for the BillingAgent
test_cases = [
    {
        "chat_history": "User: Hi, I'd like to know my next billing date.\n"
        "BillingAgent: Sure! Please provide your policy number.\n"
        "User: It's B67890.\n",
        "expected_response": "Your next payment of $300.00 is due on 2025-03-15, and your current status is 'Pending'.",
    }
]


class BillingEvaluationSignature(dspy.Signature):
    chat_history: str = dspy.InputField(desc="Full conversation context.")
    agent_response: str = dspy.InputField(desc="Agent-generated response.")
    expected_response: str = dspy.InputField(desc="Expected correct response.")

    judgment: bool = dspy.OutputField(desc="Pass (True) or Fail (False).")
    reasoning: str = dspy.OutputField(desc="Detailed justification in Markdown.")
    precision_score: float = dspy.OutputField(desc="Precision score (0.0 to 1.0).")


test_agent = Agent("TestBillingAgent")
test_channel = Channel("agents")
human_channel = Channel("human")

event_received = asyncio.Event()
received_event = None


@test_agent.subscribe(
    channel=human_channel,
    filter_func=lambda event: event.get("type") == "agent_message",
)
async def handle_response(event):
    logger.info(f"Received event: {event}")
    global received_event
    received_event = event
    event_received.set()


@pytest.mark.asyncio
async def test_billing_agent():
    await billing_agent.start()
    await test_agent.start()

    for case in test_cases:
        event_received.clear()

        # Simulate a billing request event
        await test_channel.publish(
            {
                "id": str(uuid4()),
                "type": "billing_request",
                "meta": {},
                "payload": {
                    "chat_messages": [
                        {
                            "role": "User",
                            "content": "Hi, I'd like to know my next billing date.",
                        },
                        {
                            "role": "BillingAgent",
                            "content": "Sure! Please provide your policy number.",
                        },
                        {"role": "User", "content": "It's B67890."},
                    ]
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
        assert received_event["type"] == "agent_message", (
            "Unexpected event type received."
        )
        assert isinstance(received_event["payload"], str), "Payload should be a string."

        agent_response = received_event["payload"]

        # Evaluate the response
        eval_model = dspy.asyncify(dspy.Predict(BillingEvaluationSignature))
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
