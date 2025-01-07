import os
from typing import Literal

import dspy
import dotenv

# Load environment variables from .env file
dotenv.load_dotenv()

# Define valid target agents for classification
TargetAgent = Literal["PolicyAgent", "TicketingAgent", "TriageAgent"]

# Configure the language model for the classification task
language_model = dspy.LM("openai/gpt-4o-mini", cache=False)
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


# Instantiate a Chain of Thought classifier
default_classifier = dspy.ChainOfThought(signature=AgentClassificationSignature)
optimized_classifier = dspy.ChainOfThought(signature=AgentClassificationSignature)

# Load optimized configuration for the classifier
optimized_config_path = os.path.join(
    os.path.dirname(__file__), "optimized_classifier_bootstrap.json"
)
optimized_classifier.load(optimized_config_path)

if __name__ == "__main__":
    # Example usage for classification
    example_input = "User: How can I update my contact information?"
    default_classifier(chat_history=example_input)

    # Inspect history of the language model interactions
    language_model.inspect_history()
