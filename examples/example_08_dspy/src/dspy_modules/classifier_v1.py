from typing import Literal

import dspy
from dotenv import load_dotenv

from examples.example_08_dspy.src.dspy_modules.lm import language_model
from examples.example_08_dspy.src.dspy_modules.utils import run_and_calculate_costs

TargetAgent = Literal["PolicyAgent", "TicketingAgent", "TriageAgent"]

dspy.configure(lm=language_model)


class AgentClassificationSignature(dspy.Signature):
    chat_history: str = dspy.InputField()
    target_agent: TargetAgent = dspy.OutputField()
    confidence: float = dspy.OutputField()


classifier = dspy.ChainOfThought(signature=AgentClassificationSignature)

if __name__ == "__main__":
    load_dotenv()
    run_and_calculate_costs(
        classifier,
        chat_history="User: I need help with my policy."
    )
