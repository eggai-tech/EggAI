import json
import dspy
from dotenv import load_dotenv
from dspy import MIPROv2

from dspy.teleprompt import BootstrapFewShotWithRandomSearch

from examples.example_08_dspy.src.classifier import classifier


def load_data(path: str = "../datasets/triage-training.json"):
    """
    Loads the dataset and constructs the devset list of dspy.Example objects.

    :param path: Path to the triage-training JSON file.
    :return: A list of dspy.Example objects.
    """
    with open(path, "r") as f:
        ds_data = json.load(f)
    devset = []
    for ex in ds_data:
        devset.append(
            dspy.Example(
                chat_history=ex["conversation"],
                target_agent=ex["target"]
            ).with_inputs("chat_history")
        )
    return devset


def metric(example, pred, trace=None) -> bool:
    """
    A simple metric function returning True if the predicted agent matches
    the target agent (case-insensitive).

    :param example: The original example object (with true target).
    :param pred: The predicted example object (with predicted target).
    :param trace: Optional trace for debugging or detailed output.
    :return: True if prediction matches target; otherwise False.
    """
    return example.target_agent.lower() == pred.target_agent.lower()


def run_evaluation(program, devset):
    """
    Runs evaluation of the classifier over the given devset.

    :param devset: A list of dspy.Example objects to evaluate against.
    """
    evaluator = dspy.evaluate.Evaluate(
        devset=devset,
        num_threads=10,
        display_progress=True,
        return_outputs=True,
        return_all_scores=True
    )
    score, results, all_scores = evaluator(program, metric=metric)
    print("Final score:", score)
    # print("Results:", results)

    # print failed examples where the prediction did not match the target
    for example, pred, score in results:
        if not score:
            print("Failed example:", example)
            print("Prediction:", pred)



def optimize(trainset):
    """
    Optimizes the classifier using the MIPROv2 optimizer.

    :param trainset: A list of dspy.Example objects used for optimization.
    """
    teleprompter = BootstrapFewShotWithRandomSearch(
        metric=metric,
        max_labeled_demos=20,
        num_threads=20,
        max_bootstrapped_demos=20
    )
    optimized_program = teleprompter.compile(classifier, trainset=trainset)

    optimized_program.save("optimized_classifier_bootstrap.json")

    run_evaluation(optimized_program, trainset)


def main():
    """
    Main entry point: load environment variables, load data, run evaluation, and optimize.
    """
    load_dotenv()
    devset = load_data()
    run_evaluation(classifier, devset)
    optimize(devset)


if __name__ == "__main__":
    main()
