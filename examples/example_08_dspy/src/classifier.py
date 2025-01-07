import os
from typing import Literal

import dspy

import dotenv

dotenv.load_dotenv()

TargetAgent = Literal["PolicyAgent", "TicketingAgent", "TriageAgent"]

lm = dspy.LM("openai/gpt-4o-mini", cache=False)
dspy.configure(lm=lm)


class ClassificationSignature(dspy.Signature):
    """
    You are a Triage agent in a multi-agent insurance support system.
    Your primary responsibility is to route messages to the appropriate target agent.
    There are following target agents to route to: PolicyAgent, TicketingAgent and TriageAgent.
    If the request is insurance related but you are not sure where to route it to, route it to the TicketingAgent.
    If the request is not insurance related route to TriageAgent.
    """

    chat_history: str = dspy.InputField(desc="The full chat history for context.")
    target_agent: TargetAgent = dspy.OutputField(desc="The target agent to triage to.")
    confidence: float = dspy.OutputField(desc="The confidence score (between 0.0 and 1.0) for the target agent selection.")

classifier = dspy.ChainOfThought(signature=ClassificationSignature)

optimized_classifier = dspy.ChainOfThought(signature=ClassificationSignature)
# path get current dir from import + optimized_classifier_bootstrap.json
optimized_conf_path = os.path.join(
    os.path.dirname(__file__), "optimized_classifier_bootstrap.json"
)

optimized_classifier.load(optimized_conf_path)

if __name__ == "__main__":
    optimized_classifier(chat_history="User: How can I update my contact information?")
    lm.inspect_history()
