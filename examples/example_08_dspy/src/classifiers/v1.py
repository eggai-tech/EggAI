from typing import Literal

import dspy

TargetAgent = Literal["PolicyAgent", "TicketingAgent", "TriageAgent"]

language_model = dspy.LM("openai/gpt-4o-mini")
dspy.configure(lm=language_model)


class AgentClassificationSignature(dspy.Signature):
    chat_history: str = dspy.InputField()
    target_agent: TargetAgent = dspy.OutputField()
    confidence: float = dspy.OutputField()

classifier = dspy.ChainOfThought(signature=AgentClassificationSignature)
