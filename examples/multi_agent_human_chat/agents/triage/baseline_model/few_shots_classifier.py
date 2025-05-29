import pickle
from pathlib import Path
from typing import Optional

import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.linear_model import LogisticRegression

from agents.triage.baseline_model.utils import sample_training_examples


class FewShotsClassifier:
    """
    Simple few-shot linear classifier for classifying incoming messages based on SentenceTransformer embeddings.
    SentenceTransformer is used to compute embeddings for the instructions, and LogisticRegression is used on top
    of the embeddings to classify the instructions.

    Args:
            n_classes: Number of message classes. This parameter is optional and can be set to None.
            n_examples: Number of examples per class for training. If None, use all examples.
            seeds: Random seeds for sampling training examples. If more than one seed is provided, multiple
                classifiers will be trained and treated as an ensemble.
            C: LogisticRegression regularization strength. Must be a positive float, small values specify stronger regularization.
            st_model_name: Name of the SentenceTransformer model.
    """

    def __init__(
        self,
        n_classes: Optional[int] = None,
        n_examples: Optional[int] = None,
        seeds: int | list[int] = 47,
        C: float = 1.0,
        st_model_name: str = "all-MiniLM-L12-v2",
    ):
        self.n_classes = n_classes
        self.n_examples = n_examples
        self.seeds = seeds
        self.sentence_transformer = SentenceTransformer(st_model_name)
        self.C = C
        # initialize the ensemble of classifiers
        self.classifiers = []

    def fit(self, dataset: dict[str, int]):
        """
        Train an ensemble of classifiers on the training data.

        Args:
            dataset: Dataset containing the training data. The dataset should be a dictionary where the keys are
                the instruction strings and the values are the corresponding class labels.
        """
        if isinstance(self.seeds, int) or self.n_examples is None:
            # if n_examples is None we train a single classifier on the whole training set
            seeds = [self.seeds]
        else:
            seeds = self.seeds

        # create a classifier for each seed
        for seed in seeds:
            # sample training examples; if n_examples is None, use all examples
            instructions, y = sample_training_examples(dataset, self.n_examples, seed)
            # compute instruction embeddings with SentenceTransformer
            X = self.sentence_transformer.encode(instructions)
            # create and train the logistic regression classifier
            if self.n_examples is None:
                # use class_weight="balanced" to handle class imbalance
                class_weight = "balanced"
            else:
                # if n_examples is not None, we sample the training set and the class distribution is balanced
                class_weight = None
            logistic_regression = LogisticRegression(
                penalty="l2",
                C=self.C,
                solver="lbfgs",
                max_iter=1000,
                class_weight=class_weight,
            )
            logistic_regression.fit(X, y)
            # add the classifier to the ensemble
            self.classifiers.append(logistic_regression)

    def __call__(self, instructions: list[str]) -> np.array:
        """
        Predict class probabilities using the linear classifier.
        If multiple classifiers are trained, average their predictions.

        Args:
            instructions: List of instructions.

        Returns:
            y_pred: predicted class probabilities of size (n_samples, n_classes)
        """

        X = self.sentence_transformer.encode(instructions)
        y_pred = [classifier.predict_proba(X) for classifier in self.classifiers]
        # stack the predictions from all classifiers
        y_pred = np.stack(y_pred)
        # average the predictions across classifiers
        y_pred = y_pred.mean(axis=0)

        # return the predicted class probabilities
        return y_pred

    def save(self, checkpoint_dir: str, name: Optional[str] = None) -> Path:
        """
        Save the model to a file.

        Args:
            checkpoint_dir: Directory to save the model.

        Returns:
            output_path: Path to the saved model.
            name: Name of the model. If None, generate a name based on the number of examples and seed.
        """
        # create checkpoint_dir if it does not exist
        checkpoint_dir = Path(checkpoint_dir)
        checkpoint_dir.mkdir(parents=True, exist_ok=True)
        if name is None:
            name = f"fewshot_classifier_n_{self.n_examples}"
        output_path = checkpoint_dir / f"{name}.pkl"
        with open(output_path, "wb") as f:
            pickle.dump(self.classifiers, f)

        return output_path

    @staticmethod
    def load(input_path: str) -> "FewShotsClassifier":
        """
        Load the model from a file and returns a FewShotsClassifier instance.

        Args:
            input_path: Path to load the model.
        """
        with open(input_path, "rb") as f:
            loaded = pickle.load(f)
            if not isinstance(loaded, FewShotsClassifier):
                raise ValueError(
                    f"Loaded object is not a FewShotsClassifier: {type(loaded)}"
                )
            return loaded
