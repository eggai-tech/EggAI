from typing import Literal

import dspy
from dotenv import load_dotenv

from .lm import language_model
from .utils import run_and_calculate_costs

TargetAgent = Literal["PolicyAgent", "TicketingAgent", "TriageAgent"]

dspy.configure(lm=language_model)


class AgentClassificationSignature(dspy.Signature):
    """
    Extract the intent of a user message and classify it to the appropriate target agent.

    Available Target Agents:
    - PolicyAgent: Handles policy-related queries.
    - TicketingAgent: Handles insurance related queries for customer support (e.g. contact information).
    - TriageAgent: Handles non-insurance-related queries.

    Fallback Rules:
    - Route to TicketingAgent if unsure where to send an insurance-related query.
    - Route to TriageAgent if the query is not insurance-related.
    """

    chat_history: str = dspy.InputField(
        desc="Full chat history providing context for the classification process."
    )

    target_agent: TargetAgent = dspy.OutputField(
        desc="Target agent classified for triage based on context and rules."
    )


intent_classifier = dspy.ChainOfThought(signature=AgentClassificationSignature)

if __name__ == "__main__":
    load_dotenv()
    run_and_calculate_costs(
        intent_classifier,
        chat_history="User: I need help with my policy."
    )
