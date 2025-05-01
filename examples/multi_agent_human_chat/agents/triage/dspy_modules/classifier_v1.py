import dspy
from dotenv import load_dotenv

from agents.triage.models import formatted_agent_registry, TargetAgent

from agents.triage.config import Settings
from libraries.dspy_set_language_model import dspy_set_language_model

load_dotenv()

settings = Settings()

lm = dspy_set_language_model(settings)

class AgentClassificationSignature(dspy.Signature):
    """
    Represents the input and output fields for the agent classification process.

    Role:
    - Acts as a Triage agent in a multi-agent insurance support system.

    Responsibilities:
    - Classifies and routes messages to appropriate target agents based on context.

    Target Agents:
    """+formatted_agent_registry()+"""

    Fallback Rules:
    - Route to ChattyAgent if the query is not insurance-related.
    """

    # Input Fields
    chat_history: str = dspy.InputField(
        desc="Full chat history providing context for the classification process."
    )

    # Output Fields
    target_agent: TargetAgent = dspy.OutputField(
        desc="Target agent classified for triage based on context and rules."
    )


classifier_v1 = dspy.ChainOfThought(signature=AgentClassificationSignature)

if __name__ == "__main__":
    res = classifier_v1(
        chat_history="User: hello!",
    )
    print(res.target_agent)
    lm.inspect_history()
