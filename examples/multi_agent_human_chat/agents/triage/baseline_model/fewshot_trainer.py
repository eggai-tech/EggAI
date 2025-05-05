import logging
import os
import sys

import mlflow
from dotenv import load_dotenv
from sklearn.metrics import confusion_matrix, accuracy_score

from agents.triage.baseline_model.config import settings
from agents.triage.baseline_model.few_shots_classifier import FewShotsClassifier
from agents.triage.baseline_model.metrics import compute_f1_score, compute_roc_auc
from agents.triage.baseline_model.utils import load_dataset, load_datasets, init_mlflow, setup_logging, \
    CATEGORY_LABEL_MAP

logger = logging.getLogger("fewshot_trainer")

load_dotenv()


def main() -> int:
    # Print current working directory
    logger.info(f"Current working directory: {os.getcwd()}")

    # Initialize MLflow
    init_mlflow(settings.mlflow_config_dict)

    # Load triage dataset
    logger.info(f"Loading dataset from {settings.train_dataset_paths}")
    train_dataset = load_datasets(settings.train_dataset_paths)

    if isinstance(settings.seed, int):
        seeds = [settings.seed]
    else:
        assert len(settings.seed) > 1
        seeds = settings.seed

    # Create few-shot classifier
    fewshot_classifier = FewShotsClassifier(
        n_classes=settings.n_classes,
        n_examples=settings.n_examples,
        seeds=seeds,
    )

    # Train the classifier
    logger.info(f"Training few-shot classifier with {settings.n_examples} examples per class")
    fewshot_classifier.fit(train_dataset)

    # Evaluate on the test set
    logger.info(f"Evaluating few-shot classifier on test set")
    test_dataset = load_dataset(settings.test_dataset_path)
    # Get instructions and labels, by splitting keys and values
    X_test, y_test = list(test_dataset.keys()), list(test_dataset.values())

    # Predict class probabilities
    y_pred = fewshot_classifier(X_test)

    # Compute metrics
    f1 = compute_f1_score(y_test, y_pred, settings.n_classes)
    auc = compute_roc_auc(y_test, y_pred)
    acc = accuracy_score(y_test, y_pred.argmax(axis=1))

    # Compute per-class accuracy
    cm = confusion_matrix(y_test, y_pred.argmax(axis=1), labels=list(range(settings.n_classes)))
    per_class_acc = cm.diagonal() / cm.sum(axis=1)

    # Log results
    logger.info(f"F1 score: {f1:.4f}")
    logger.info(f"AUC score: {auc:.4f}")
    logger.info(f"Accuracy score: {acc:.4f}")
    logger.info(f"Per-class accuracy: {per_class_acc}")
    logger.info("Confusion matrix:")
    logger.info(cm)

    # Log results to mlflow
    mlflow.log_metric("f1", f1)
    mlflow.log_metric("auc", auc)
    mlflow.log_metric("accuracy", acc)
    for k, acc in zip(CATEGORY_LABEL_MAP.keys(), per_class_acc):
        mlflow.log_metric(f"{k}_accuracy", acc)

    # Save the model in the model registry
    n_examples = settings.n_examples if settings.n_examples else "all"
    model_name = settings.model_name_template.format(n_examples=n_examples)

    logger.info(f"Saving model {model_name} to the MLflow registry")
    mlflow.sklearn.log_model(
        sk_model=fewshot_classifier,
        artifact_path="model",
        registered_model_name=model_name,
    )
    return 0


if __name__ == "__main__":
    setup_logging()
    sys.exit(main())
