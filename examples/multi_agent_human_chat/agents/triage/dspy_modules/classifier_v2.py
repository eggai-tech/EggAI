import os

import dspy
from dotenv import load_dotenv

from agents.triage.config import Settings
from agents.triage.dspy_modules.classifier_v1 import classifier_v1, AgentClassificationSignature

settings = Settings()

load_dotenv()
lm = dspy.LM(settings.language_model, cache=settings.cache_enabled)
dspy.configure(lm=lm)

classifier_v3_json_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "optimizations_v2.json"))

classifier_v2 = dspy.ChainOfThought(signature=AgentClassificationSignature)
classifier_v2.load(classifier_v3_json_path)

if __name__ == "__main__":
    load_dotenv()
    res = classifier_v2(
        chat_history="User: hello!",
    )
    print(res.target_agent)
