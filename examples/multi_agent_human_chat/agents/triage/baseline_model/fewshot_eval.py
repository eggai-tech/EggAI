import logging
import sys

import hydra
import mlflow
from omegaconf import DictConfig
from sklearn.metrics import confusion_matrix, accuracy_score

from agents.triage.baseline_model.few_shots_classifier import FewShotsClassifier
from agents.triage.baseline_model.metrics import compute_f1_score, compute_roc_auc
from agents.triage.baseline_model.utils import load_dataset, setup_logging, init_mlflow, \
    CATEGORY_LABEL_MAP

logger = logging.getLogger("fewshot_eval")


@hydra.main(config_path="configs", config_name="fewshot_eval_config")
def main(cfg: DictConfig) -> int:
    init_mlflow(cfg)
    # load test dataset
    test_dataset = load_dataset(cfg.dataset.path)
    # get instructions and labels, by splitting keys and values
    X_test, y_test = list(test_dataset.keys()), list(test_dataset.values())

    # load the model from the model registry
    if "artifact_uri" in cfg.model:
        model_path = mlflow.artifacts.download_artifacts(cfg.model.artifact_uri)
    else:
        model_path = cfg.model.path
    logger.info(f"Loading model from the registry: {model_path}")
    # load few-shot classifier
    fewshot_classifier = FewShotsClassifier()
    fewshot_classifier.load(model_path)
    logger.info(f"Evaluating model on test set from {cfg.dataset.path}")

    # predict class probabilities
    y_pred = fewshot_classifier(X_test)
    # compute auc and f1 score
    f1 = compute_f1_score(y_test, y_pred, cfg.model.n_classes)
    auc = compute_roc_auc(y_test, y_pred)
    acc = accuracy_score(y_test, y_pred.argmax(axis=1))
    # compute per-class accuracy
    cm = confusion_matrix(y_test, y_pred.argmax(axis=1), labels=list(range(cfg.model.n_classes)))
    per_class_acc = cm.diagonal() / cm.sum(axis=1)
    logger.info(f"F1 score: {f1:.4f}")
    logger.info(f"AUC score: {auc:.4f}")
    logger.info(f"Accuracy score: {acc:.4f}")
    logger.info(f"Per-class accuracy: {per_class_acc}")
    logger.info("Confusion matrix:")
    logger.info(cm)

    # save results
    results = {
        "f1": f1,
        "auc": auc,
        "accuracy": acc,
        "per_class_accuracy": per_class_acc,
        "confusion_matrix": cm,
    }

    # log results to mlflow
    mlflow.log_metric("f1", f1)
    mlflow.log_metric("auc", auc)
    mlflow.log_metric("accuracy", acc)
    for k, acc in zip(CATEGORY_LABEL_MAP.keys(), per_class_acc):
        mlflow.log_metric(f"{k}_accuracy", acc)

    return 0


if __name__ == "__main__":
    setup_logging()
    sys.exit(main())
