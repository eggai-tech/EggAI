import os

import dspy
from dotenv import load_dotenv

from agents.triage.config import Settings
from agents.triage.dspy_modules.classifier_v1 import AgentClassificationSignature
from libraries.dspy_set_language_model import dspy_set_language_model

settings = Settings()

load_dotenv()
lm = dspy_set_language_model(settings)

optimizations_json = os.path.abspath(os.path.join(os.path.dirname(__file__), "optimizations_v2.json"))

classifier_v2 = dspy.ChainOfThought(signature=AgentClassificationSignature)
classifier_v2.load(optimizations_json)

if __name__ == "__main__":
    load_dotenv()
    res = classifier_v2(
        chat_history="User: hello!",
    )
    print(res.target_agent)
