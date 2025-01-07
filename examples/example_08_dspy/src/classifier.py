import json
import os
from typing import Literal

import dspy

TargetAgent = Literal["PolicyAgent", "TicketingAgent", "TriageAgent"]

lm = dspy.LM('openai/gpt-4o-mini')
dspy.configure(lm=lm)


class ClassificationSignature(dspy.Signature):
    chat_history: str = dspy.InputField(desc="The full chat history for context.")
    target_agent: TargetAgent = dspy.OutputField(desc="The target agent to triage to.")


classifier = dspy.ChainOfThought(
    signature=ClassificationSignature
)

optimized_classifier = dspy.ChainOfThought(
    signature=ClassificationSignature
)
#path get current dir from import + optimized_classifier_bootstrap.json
optimized_conf_path = os.path.join(os.path.dirname(__file__), 'optimized_classifier_bootstrap.json')

optimized_classifier.load(optimized_conf_path)