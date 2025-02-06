import os

import dspy
from dotenv import load_dotenv

from agents.triage.evaluation.report import generate_report
import csv


def load_dataset(filename: str) -> list:
    csv_file_path = os.path.abspath(
        os.path.join(os.path.dirname(__file__), f"{filename}.csv")
    )
    dataset = []

    with open(csv_file_path, "r", newline="", encoding="utf-8") as csvfile:
        reader = csv.DictReader(csvfile)
        next(reader, None)
        for row in reader:
            conversation = row["conversation"].replace("\\n", "\n").replace('"', "")
            target = row["target"].replace("\\n", "\n").replace('"', "")
            dataset.append({
                "conversation": conversation,
                "target": target
            })

    return dataset

def load_data(file: str):
    devset = []
    for ex in load_dataset(file):
        devset.append(
            dspy.Example(
                chat_history=ex["conversation"],
                target_agent=ex["target"],
                small_talk_message="s",
                fall_back_message="s"
            ).with_inputs("chat_history")
        )
    return devset

def run_evaluation(program, devset):
    evaluator = dspy.evaluate.Evaluate(
        devset=devset,
        num_threads=10,
        display_progress=True,
        return_outputs=True,
        return_all_scores=True
    )
    score, results, all_scores = evaluator(program, metric=lambda example, pred,
                                                                  trace=None: example.target_agent.lower() == pred.target_agent.lower())
    return score, results

def run_evaluation_v1():
    load_dotenv()
    language_model = dspy.LM("openai/gpt-4o-mini", cache=True)
    dspy.configure(lm=language_model)

    from agents.triage.dspy_modules.v1 import triage_classifier as classifier_v1
    test_dataset = load_data("triage-testing")
    score_v1, results_v1 = run_evaluation(classifier_v1, test_dataset)
    generate_report(results_v1, "classifier_v1")
    return score_v1


if __name__ == "__main__":
    score = run_evaluation_v1()
    print(f"Accuracy: {score}")
