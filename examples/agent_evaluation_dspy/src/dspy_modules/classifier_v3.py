import os
from typing import Literal

import dspy
from dotenv import load_dotenv

from .classifier_v2 import AgentClassificationSignature, classifier as classifier_v2
from .lm import language_model
from .utils import run_and_calculate_costs

TargetAgent = Literal["PolicyAgent", "TicketingAgent", "TriageAgent"]

dspy.configure(lm=language_model)

classifier_v3_json_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "optimizations_v3.json"))


def load():
    classifier = dspy.ChainOfThought(signature=AgentClassificationSignature)
    classifier.load(classifier_v3_json_path)
    return classifier


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
    classifier = load()
    run_and_calculate_costs(
        classifier,
        chat_history="User: I need help with my policy."
    )
