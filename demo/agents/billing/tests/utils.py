import dspy

from libraries.observability.logger import get_console_logger
from libraries.testing.utils import (
    MLflowTracker as MLflowTracker,
)
from libraries.testing.utils import (
    create_conversation_string,
    create_message_list,
)
from libraries.testing.utils import (
    setup_mlflow_tracking as setup_mlflow_tracking,
)

logger = get_console_logger("billing_agent.tests.utils")

class BillingEvaluationSignature(dspy.Signature):
    """DSPy signature for LLM-based evaluation of billing agent responses."""

    chat_history: str = dspy.InputField(desc="Full conversation context.")
    agent_response: str = dspy.InputField(desc="Agent-generated response.")
    expected_response: str = dspy.InputField(desc="Expected correct response.")

    judgment: bool = dspy.OutputField(desc="Pass (True) or Fail (False).")
    reasoning: str = dspy.OutputField(desc="Detailed justification in Markdown.")
    precision_score: float = dspy.OutputField(desc="Precision score (0.0 to 1.0).")

def get_test_cases():
    test_cases = [
        {
            "policy_number": "B67890",
            "expected_response": "Your next payment of $300.00 is due on 2026-03-15.",
            "user_messages": [
                "Hi, I'd like to know my next billing date.",
                "It's B67890.",
            ],
            "agent_responses": ["Sure! Please provide your policy number."],
        },
        {
            "policy_number": "A12345",
            "expected_response": "Your current amount due is $120.00 with a due date of 2026-02-01.",
            "user_messages": ["How much do I owe on my policy?", "A12345"],
            "agent_responses": [
                "I'd be happy to check that for you. Could you please provide your policy number?"
            ],
        },
        {
            "policy_number": "C24680",
            "expected_response": "Your billing cycle has been successfully changed to Monthly.",
            "user_messages": ["I want to change my billing cycle.", "C24680"],
            "agent_responses": [
                "I can help you with that. May I have your policy number please?"
            ],
        },
    ]

    for case in test_cases:
        case["chat_messages"] = create_message_list(
            case["user_messages"], case.get("agent_responses"),
            agent_role="BillingAgent"
        )

        case["chat_history"] = create_conversation_string(case["chat_messages"])

    return test_cases

# Import wait_for_agent_response from shared test utils
from libraries.testing.utils import wait_for_agent_response as _wait_for_agent_response


async def wait_for_agent_response(
    response_queue, connection_id: str, timeout: float = 30.0
) -> dict:
    """Wait for a response from the billing agent with matching connection ID."""
    return await _wait_for_agent_response(
        response_queue, connection_id, timeout, expected_source="billing_agent"
    )

async def evaluate_response_with_llm(
    chat_history, expected_response, agent_response, dspy_lm
):
    """Evaluate agent response against the expected response using LLM."""
    # Evaluate using LLM
    eval_model = dspy.asyncify(dspy.Predict(BillingEvaluationSignature))
    with dspy.context(lm=dspy_lm):
        evaluation_result = await eval_model(
            chat_history=chat_history,
            agent_response=agent_response,
            expected_response=expected_response,
        )

    return evaluation_result
