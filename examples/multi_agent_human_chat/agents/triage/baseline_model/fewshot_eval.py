import logging
import sys

import mlflow
from sklearn.metrics import confusion_matrix, accuracy_score

from agents.triage.baseline_model.few_shots_classifier import FewShotsClassifier
from agents.triage.baseline_model.metrics import compute_f1_score, compute_roc_auc
from agents.triage.baseline_model.utils import load_dataset, setup_logging, init_mlflow, \
    CATEGORY_LABEL_MAP
from agents.triage.baseline_model.config import settings

logger = logging.getLogger("fewshot_eval")


def main() -> int:
    # Initialize MLflow with our config
    init_mlflow(settings.mlflow_config_dict)
    
    # Load test dataset
    test_dataset = load_dataset(settings.eval_dataset_path)
    # Get instructions and labels, by splitting keys and values
    X_test, y_test = list(test_dataset.keys()), list(test_dataset.values())

    # Load the model from the model registry
    if settings.model_artifact_uri:
        model_path = mlflow.artifacts.download_artifacts(settings.model_artifact_uri)
    else:
        model_path = settings.model_path
    
    logger.info(f"Loading model from the registry: {model_path}")
    # Load few-shot classifier
    fewshot_classifier = FewShotsClassifier()
    fewshot_classifier.load(model_path)
    logger.info(f"Evaluating model on test set from {settings.eval_dataset_path}")

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

    # Save results
    results = {
        "f1": f1,
        "auc": auc,
        "accuracy": acc,
        "per_class_accuracy": per_class_acc,
        "confusion_matrix": cm,
    }

    # Log results to mlflow
    mlflow.log_metric("f1", f1)
    mlflow.log_metric("auc", auc)
    mlflow.log_metric("accuracy", acc)
    for k, acc in zip(CATEGORY_LABEL_MAP.keys(), per_class_acc):
        mlflow.log_metric(f"{k}_accuracy", acc)

    return 0


if __name__ == "__main__":
    setup_logging()
    sys.exit(main())
