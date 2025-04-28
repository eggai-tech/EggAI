import os

import dspy
from dotenv import load_dotenv

from .classifier_v2 import AgentClassificationSignature, classifier_v2 as classifier_v2

lm = dspy.LM("openai/gpt-4o-mini", cache=False)
dspy.configure(lm=lm)

classifier_v3_json_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "optimizations_v3.json"))

def load_classifier_v3():
    classifier_v3 = dspy.ChainOfThought(signature=AgentClassificationSignature)
    classifier_v3.load(classifier_v3_json_path)
    return classifier_v3


def optimize(training_data_set, overwrite=False):
    if os.path.exists(classifier_v3_json_path) and overwrite is False:
        return
    teleprompter = dspy.BootstrapFewShot(
        metric=lambda example, pred, trace=None: example.target_agent.lower() == pred.target_agent.lower(),
        max_labeled_demos=22,
        max_bootstrapped_demos=22,
        max_rounds=10,
        max_errors=20
    )
    optimized_program = teleprompter.compile(classifier_v2, trainset=training_data_set)
    optimized_program.save(classifier_v3_json_path)


if __name__ == "__main__":
    load_dotenv()
    classifier = load_classifier_v3()
