import asyncio
import pytest
import dspy
from uuid import uuid4
from eggai import Agent, Channel
from ..agent import policies_agent

dspy.configure(lm=dspy.LM("openai/gpt-4o-mini"))

# Test data for the PoliciesAgent
test_cases = [
    {
        "chat_history": "User: When is my next premium payment due?\n"
                         "PoliciesAgent: Could you please provide your policy number?\n"
                         "User: B67890.\n",
        "expected_response_content": "Your next premium payment is due on February 1, 2025."
    }
]

class PolicyEvaluationSignature(dspy.Signature):
    chat_history: str = dspy.InputField(desc="Full conversation context.")
    agent_response: str = dspy.InputField(desc="Agent-generated response.")
    expected_response_content: str = dspy.InputField(desc="Expected correct response content.")

    judgment: bool = dspy.OutputField(desc="Pass (True) or Fail (False).")
    reasoning: str = dspy.OutputField(desc="Detailed justification in Markdown.")
    precision_score: float = dspy.OutputField(desc="Precision score (0.0 to 1.0).")

# Set up test agent and channels
test_agent = Agent("TestPoliciesAgent")
test_channel = Channel("agents")
human_channel = Channel("human")

event_received = asyncio.Event()
received_event = None

@test_agent.subscribe(channel=human_channel, filter_func=lambda event: event.get("type") == "agent_message")
async def handle_response(event):
    global received_event
    received_event = event
    event_received.set()

@pytest.mark.asyncio
async def test_policies_agent():
    await policies_agent.start()
    await test_agent.start()

    for case in test_cases:
        event_received.clear()

        # Simulate a policy request event
        await test_channel.publish({
            "id": str(uuid4()),
            "type": "policy_request",
            "meta": {},
            "payload": {
                "chat_messages": [
                    {"role": "User", "content": case["chat_history"].split("\n")[0]},
                    {"role": "PoliciesAgent", "content": case["chat_history"].split("\n")[1]},
                    {"role": "User", "content": case["chat_history"].split("\n")[2]}
                ]
            }
        })

        try:
            await asyncio.wait_for(event_received.wait(), timeout=5.0)
        except asyncio.TimeoutError:
            pytest.fail(f"Timeout: No response event received for chat history: {case['chat_history']}")

        assert received_event is not None, "No agent response received."
        assert received_event["type"] == "agent_message", "Unexpected event type received."
        assert isinstance(received_event["payload"], str), "Payload should be a string."

        agent_response = received_event["payload"]

        # Evaluate the response
        eval_model = dspy.asyncify(dspy.Predict(PolicyEvaluationSignature))
        evaluation_result = await eval_model(
            chat_history=case["chat_history"],
            agent_response=agent_response,
            expected_response_content=case["expected_response_content"]
        )

        assert evaluation_result.judgment, "Judgment must be True. " + evaluation_result.reasoning
        assert 0.8 <= evaluation_result.precision_score <= 1.0, "Precision score must be between 0.8 and 1.0."
