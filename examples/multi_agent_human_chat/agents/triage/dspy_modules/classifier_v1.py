import dspy
from dotenv import load_dotenv

from agents.triage.config import Settings
from agents.triage.models import ClassifierMetrics, TargetAgent
from libraries.dspy_set_language_model import dspy_set_language_model

load_dotenv()

settings = Settings()

lm = dspy_set_language_model(settings)


class AgentClassificationSignature(dspy.Signature):
    def __init__(self, chat_history: str):
        super().__init__(chat_history=chat_history)
        self.metrics: ClassifierMetrics

    chat_history: str = dspy.InputField()
    target_agent: TargetAgent = dspy.OutputField()


classifier_v1_program = dspy.Predict(signature=AgentClassificationSignature)


def classifier_v1(chat_history: str) -> AgentClassificationSignature:
    result = classifier_v1_program(chat_history=chat_history)
    result.metrics = ClassifierMetrics(
        total_tokens=lm.total_tokens,
        prompt_tokens=lm.prompt_tokens,
        completion_tokens=lm.completion_tokens,
        latency_ms=lm.latency_ms,
    )
    return result


if __name__ == "__main__":
    res = classifier_v1(
        chat_history="User: hello!",
    )
    print(res.target_agent)
    print(res.metrics)
