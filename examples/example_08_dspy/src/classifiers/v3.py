import os
from typing import Literal

import dspy

TargetAgent = Literal["PolicyAgent", "TicketingAgent", "TriageAgent"]

language_model = dspy.LM("openai/gpt-4o-mini")
dspy.configure(lm=language_model)

classifier_v3_json_path = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "optimizations_v3.json"))


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


def load_classifier():
    classifier = dspy.ChainOfThought(signature=AgentClassificationSignature)
    classifier.load(classifier_v3_json_path)
    return classifier


def optimize(program, training_data_set, overwrite=False):
    if os.path.exists(classifier_v3_json_path) and not overwrite:
        pass
    teleprompter = dspy.BootstrapFewShot(
        metric=lambda example, pred, trace=None: example.target_agent.lower() == pred.target_agent.lower(),
        max_labeled_demos=22,
        max_bootstrapped_demos=22
    )
    optimized_program = teleprompter.compile(program, trainset=training_data_set)
    optimized_program.save(classifier_v3_json_path)
