import os

import dspy

from agents.triage.dspy_modules.classifier_v1 import classifier_v1

classifier_v3_json_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "optimizations_v3.json"))

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
    optimized_program = teleprompter.compile(classifier_v1, trainset=training_data_set)
    optimized_program.save(classifier_v3_json_path)

if __name__ == "__main__":
    from dotenv import load_dotenv
    from agents.triage.dspy_modules.classifier_v1 import training_data_set
    load_dotenv()
    optimize(training_data_set, overwrite=True)