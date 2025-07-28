import numpy as np
from sklearn.metrics import roc_auc_score


def compute_f1_score(y_true: np.array, y_pred: np.array, n_classes: int) -> float:
    """
    Compute the F1 score for a multi-class classification problem.

    Args:
        y_true: True labels.
        y_pred: Predicted labels.
        n_classes: Number of classes.

    Returns:
        f1_score: F1 score.
    """
    # Convert to binary labels
    y_true_binary = np.eye(n_classes)[y_true]
    y_pred_binary = np.eye(n_classes)[y_pred.argmax(axis=1)]

    # Compute precision and recall
    tp = np.sum(y_true_binary * y_pred_binary, axis=0)
    fp = np.sum((1 - y_true_binary) * y_pred_binary, axis=0)
    fn = np.sum(y_true_binary * (1 - y_pred_binary), axis=0)

    precision = tp / (tp + fp + 1e-10)
    recall = tp / (tp + fn + 1e-10)

    # Compute F1 score
    f1_score = 2 * (precision * recall) / (precision + recall + 1e-10)
    return np.mean(f1_score)


def compute_roc_auc(y_true: np.array, y_pred: np.array) -> float:
    """
    Macro-averaged One-vs-Rest ROC AUC score for multi-class classification.

    Args:
        y_true: True labels.
        y_pred: Predicted labels.
        n_classes: Number of classes.

    Returns:
        auc: AUC score.
    """
    # Compute AUC
    auc = roc_auc_score(y_true, y_pred, average="macro", multi_class="ovr")
    return auc
