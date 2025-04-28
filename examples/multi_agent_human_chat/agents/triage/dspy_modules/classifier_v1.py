import dspy
from dotenv import load_dotenv

from agents.triage.models import TargetAgent

lm = dspy.LM("openai/gpt-4o-mini", cache=False)
dspy.configure(lm=lm)


class AgentClassificationSignature(dspy.Signature):
    chat_history: str = dspy.InputField()
    target_agent: TargetAgent = dspy.OutputField()
    confidence: float = dspy.OutputField()


classifier_v1 = dspy.ChainOfThought(signature=AgentClassificationSignature)

if __name__ == "__main__":
    load_dotenv()
    res = classifier_v1(
        chat_history="User: Hello, I need help with my insurance claim.",
    )
    print(res.target_agent)
