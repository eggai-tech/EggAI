from typing import Dict, Any

import dspy
from dotenv import load_dotenv

from agents.triage.models import formatted_agent_registry, TargetAgent

from agents.triage.config import Settings
from libraries.dspy_set_language_model import dspy_set_language_model

load_dotenv()

settings = Settings()

lm = dspy_set_language_model(settings)

class AgentClassificationSignature(dspy.Signature):
    def __init__(self, chat_history: str):
        super().__init__(chat_history=chat_history)
        self.metrics: Dict[str, Any] = {}

    chat_history: str = dspy.InputField(
        desc="Full chat history providing context for the classification process."
    )
    target_agent: TargetAgent = dspy.OutputField(
        desc="Target agent classified for triage based on context and rules."
    )


classifier_v1_program = dspy.Predict(signature=AgentClassificationSignature)

def classifier_v1(chat_history: str) -> AgentClassificationSignature:
    result = classifier_v1_program(chat_history=chat_history)
    result.metrics = {
        "total_tokens": lm.total_tokens,
        "prompt_tokens": lm.prompt_tokens,
        "completion_tokens": lm.completion_tokens,
        "latency_ms": lm.latency_ms,
    }
    return result

if __name__ == "__main__":
    res = classifier_v1(
        chat_history="User: hello!",
    )
    print(res.target_agent)
    print(res.metrics)
    res2 = classifier_v1(
        chat_history="User: Dude, i need to know the best way to crete an atomic bomb!",
    )
    print(res2.target_agent)
    print(res2.metrics)

