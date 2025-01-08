from typing import Literal

import dspy
from dotenv import load_dotenv

from examples.example_08_dspy.src.dspy_modules.lm import language_model

TargetAgent = Literal["PolicyAgent", "TicketingAgent", "TriageAgent"]

dspy.configure(lm=language_model)


class AgentClassificationSignature(dspy.Signature):
    chat_history: str = dspy.InputField()
    target_agent: TargetAgent = dspy.OutputField()
    confidence: float = dspy.OutputField()

classifier = dspy.ChainOfThought(signature=AgentClassificationSignature)

if __name__ == "__main__":
    load_dotenv()
    classifier(chat_history="User: I need help with my policy??!!!??.")
    last_history = language_model.history[-1]
    cost = last_history['cost']
    if cost:
        print(f"Cost: {cost:.10f}$")
        print(f"Run it {1 / cost:.0f} times to reach one dollar.")
    else:
        print("No cost. (cached)")

