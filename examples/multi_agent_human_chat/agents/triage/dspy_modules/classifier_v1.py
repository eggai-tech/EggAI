import dspy
from dotenv import load_dotenv

from agents.triage.models import TargetAgent

from agents.triage.config import Settings
settings = Settings()

load_dotenv()
lm = dspy.LM(settings.language_model, cache=settings.cache_enabled)
dspy.configure(lm=lm)


class AgentClassificationSignature(dspy.Signature):
    chat_history: str = dspy.InputField()
    target_agent: TargetAgent = dspy.OutputField()
    confidence: float = dspy.OutputField()


classifier_v1 = dspy.ChainOfThought(signature=AgentClassificationSignature)

if __name__ == "__main__":
    res = classifier_v1(
        chat_history="User: Hello, I need help with my insurance claim.",
    )
    print(res.target_agent)
