import os

import dspy
from dotenv import load_dotenv

from agents.triage.config import Settings
from agents.triage.models import ClassifierMetrics, TargetAgent
from libraries.dspy_set_language_model import dspy_set_language_model
from libraries.logger import get_console_logger

load_dotenv()

logger = get_console_logger("triage_classifier_v0")
settings = Settings()
lm = dspy_set_language_model(settings)


class AgentClassificationSignature(dspy.Signature):
    """Simple signature for agent classification."""

    def __init__(self, chat_history: str):
        super().__init__(chat_history=chat_history)
        self.metrics: ClassifierMetrics

    chat_history: str = dspy.InputField()
    target_agent: TargetAgent = dspy.OutputField()


# Create the classifier program with minimal instructions
classifier_v0_program = dspy.Predict(
    signature=AgentClassificationSignature.with_instructions(
        """Classify the chat history to one of the following agent types: 
    BillingAgent, PolicyAgent, ClaimsAgent, EscalationAgent, or ChattyAgent"""
    )
)


def classifier_v0(chat_history: str) -> AgentClassificationSignature:
    """Run the v0 classifier with minimal prompting."""
    result = classifier_v0_program(chat_history=chat_history)
    result.metrics = ClassifierMetrics(
        total_tokens=lm.total_tokens,
        prompt_tokens=lm.prompt_tokens,
        completion_tokens=lm.completion_tokens,
        latency_ms=lm.latency_ms,
    )

    # Log token usage when in debug mode
    if os.environ.get("TRIAGE_DEBUG") == "1":
        logger.debug(
            f"Token usage - Total: {lm.total_tokens}, "
            f"Prompt: {lm.prompt_tokens}, Completion: {lm.completion_tokens}"
        )
    return result


if __name__ == "__main__":
    test_cases = [
        "User: Hello! How are you today?",
        "User: I need to pay my bill. Can you help me?",
        "User: What does my policy cover for water damage?",
        "User: I want to file a claim for my car accident yesterday.",
        "User: I've been trying to resolve this for weeks! I need to speak to a manager!",
    ]

    logger.info("Testing minimal prompt classifier (v0) on example cases:")
    for test in test_cases:
        res = classifier_v0(chat_history=test)
        logger.info(f"Input: {test}\nClassified as: {res.target_agent}\n")
