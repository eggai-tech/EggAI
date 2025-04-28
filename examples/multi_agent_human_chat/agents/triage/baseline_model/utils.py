import numpy as np


def sample_training_examples(dataset: dict[str, int], n_examples: int, seed: int) -> tuple[list[str], list[int]]:
    """
    Sample n_examples examples per class.

    Args:
        dataset: Dataset containing the training data. The dataset should be a dictionary where the keys are
            the instruction strings and the values are the corresponding class labels.
        n_examples: Number of examples per class.
        seed: Random seed for sampling.

    Returns:
        A tuple containing:
        X_sampled: Sampled training data.
        y_sampled: Sampled training labels.
    """
    if n_examples is None:
        # return all examples
        return list(dataset.keys()), list(dataset.values())
    rs = np.random.RandomState(seed)
    X_sampled = []
    y_sampled = []
    for label in set(dataset.values()):
        label_instructions = [instr for instr, label in dataset.items() if label == label]
        sampled = rs.choice(label_instructions, size=n_examples, replace=False)
        X_sampled.extend(sampled.tolist())
        y_sampled.extend([label] * n_examples)
    return X_sampled, y_sampled
