from typing import Literal, Optional
import dspy

from libraries.tracing import TracedChainOfThought, create_tracer
from libraries.logger import get_console_logger
from agents.triage.config import settings

tracer = create_tracer("triage_agent", "dspy_modules")
logger = get_console_logger("triage_agent.dspy_modules")

TargetAgent = Literal["PoliciesAgent", "BillingAgent", "TicketingAgent", "TriageAgent"]


class AgentClassificationSignature(dspy.Signature):
    (
        """
    Represents the input and output fields for the agent classification process.

    Role:
    - Acts as a Triage agent in a multi-agent insurance support system.

    Responsibilities:
    - Classifies and routes messages to appropriate target agents based on context.
    - Handles small talk or casual greetings directly.

    Target Agents:
    """
        + "".join([f"\n- {agent}: {desc.get('description', '')}" for agent, desc in settings.agent_registry.items()])
        + """

    Smalltalk Rules:
    - Route to TriageAgent if the target agent is not recognized.
    - Respond to small talk or casual greetings with a friendly message, such as: 'Hello! 👋 How can I assist you with your insurance today? Feel free to ask about policies, billing, claims, or anything else!'

    Fallback Rules:
    - Route to TriageAgent if the target agent is not recognized.
    - Provide helpful guidance if the message intent is not recognized.
    """
    )

    # Input Fields
    chat_history: str = dspy.InputField(
        desc="Full chat history providing context for the classification process."
    )

    # Output Fields
    target_agent: TargetAgent = dspy.OutputField(
        desc="Target agent classified for triage based on context and rules."
    )

    small_talk_message: Optional[str] = dspy.OutputField(
        desc="A friendly response to small talk or casual greetings if small talk intent is identified."
    )

    fall_back_message: Optional[str] = dspy.OutputField(
        desc="A kind message to the user explaining why the message was not understood."
    )


logger.info("Initializing triage classifier module")
triage_classifier = TracedChainOfThought(
    signature=AgentClassificationSignature, name="triage_classifier", tracer=tracer
)
logger.debug("Triage classifier initialized with the following agent registry:")
for agent, details in settings.agent_registry.items():
    logger.debug(f"  - {agent}: {details.get('description', 'No description')}")
