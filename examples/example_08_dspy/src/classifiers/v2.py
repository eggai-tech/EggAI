from typing import Literal

import dspy

TargetAgent = Literal["PolicyAgent", "TicketingAgent", "TriageAgent"]

language_model = dspy.LM("openai/gpt-4o-mini")
dspy.configure(lm=language_model)


class AgentClassificationSignature(dspy.Signature):
    """
    Represents the input and output fields for the agent classification process.

    Role:
    - Acts as a Triage agent in a multi-agent insurance support system.

    Responsibilities:
    - Classifies and routes messages to appropriate target agents based on context.

    Target Agents:
    - PolicyAgent: Handles policy-related queries.
    - TicketingAgent: Handles unresolved insurance-related queries.
    - TriageAgent: Handles non-insurance-related queries.

    Fallback Rules:
    - Route to TicketingAgent if unsure where to send an insurance-related query.
    - Route to TriageAgent if the query is not insurance-related.
    """

    # Input Fields
    chat_history: str = dspy.InputField(
        desc="Full chat history providing context for the classification process."
    )

    # Output Fields
    target_agent: TargetAgent = dspy.OutputField(
        desc="Target agent classified for triage based on context and rules."
    )
    confidence: float = dspy.OutputField(
        desc="Confidence score (0.0 - 1.0) indicating certainty in classification."
    )

classifier = dspy.ChainOfThought(signature=AgentClassificationSignature)