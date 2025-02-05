import os

import dspy
from dotenv import load_dotenv

from agents.triage.evaluation.report import generate_report


def load_dataset(file: str) -> list:
    csv_file_path = os.path.abspath(os.path.join(os.path.dirname(__file__), file + ".csv"))

    with open(csv_file_path, "r") as file:
        data = file.readlines()
        return [
            {
                "conversation": line.strip().split(",")[0].replace('"', "").replace("\\n", "\n"),
                "target": line.strip().split(",")[1].replace('"', "").replace("\\n", "\n")
            }
            for line in data[1:]
        ]

def load_data(file: str):
    devset = []
    for ex in load_dataset(file):
        devset.append(
            dspy.Example(
                chat_history=ex["conversation"],
                target_agent=ex["target"],
                small_talk_message="",
                fall_back_message=""
            ).with_inputs("chat_history")
        )
    return devset

def run_evaluation(program, devset):
    evaluator = dspy.evaluate.Evaluate(
        devset=devset,
        num_threads=10,
        display_progress=False,
        return_outputs=True,
        return_all_scores=True
    )
    score, results, all_scores = evaluator(program, metric=lambda example, pred,
                                                                  trace=None: example.target_agent.lower() == pred.target_agent.lower())
    return score, results

def run_evaluation_v1():
    load_dotenv()

    from agents.triage.dspy_modules.v1 import AgentClassificationSignature as classifier_v1
    test_dataset = load_data("triage-testing")
    score_v1, results_v1 = run_evaluation(classifier_v1, test_dataset)
    generate_report(results_v1, "classifier_v1")


if __name__ == "__main__":
    run_evaluation_v1()