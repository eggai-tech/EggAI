import dspy

from src.loader import load_dataset


def load_data(file: str):
    """
    Loads the dataset and constructs the devset list of dspy.Example objects.

    :param path: Path to the triage-training JSON file.
    :return: A list of dspy.Example objects.
    """
    devset = []
    for ex in load_dataset(file):
        devset.append(
            dspy.Example(
                chat_history=ex["conversation"],
                target_agent=ex["target"]
            ).with_inputs("chat_history")
        )
    return devset


def run_evaluation(program, devset):
    """
    Runs evaluation of the classifier over the given devset.

    :param devset: A list of dspy.Example objects to evaluate against.
    """
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
