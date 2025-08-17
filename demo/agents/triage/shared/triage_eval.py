from dataclasses import dataclass
from typing import Protocol

from agents.triage.data_sets.loader import DatasetRow
from agents.triage.models import ClassifierMetrics, TargetAgent


@dataclass
class ClassificationResult:
    target_agent: TargetAgent
    metrics: ClassifierMetrics


class TriageClassifier(Protocol):
    def classify(self, chat_history: str) -> ClassificationResult:
        """Classify the chat history and return the target agent and metrics."""
        pass


def evaluate_classifier(
        classifier: TriageClassifier,
        test_data: list[DatasetRow]
) -> tuple[dict[str, float], list[dict[str, any]]]:
    """Evaluate the classifier on the provided test data."""
    results = []
    for row in test_data:
        chat_history = row.conversation
        target_agent = row.target_agent

        result = classifier.classify(chat_history)
        is_correct = result.target_agent == target_agent

        results.append(
            {
                "conversation": chat_history,
                "expected_agent": target_agent,
                "predicted_agent": result.target_agent,
                "metrics": result.metrics,
                "is_correct": is_correct
            }
        )

    # Calculate overall metrics
    total_cases = len(results)
    if total_cases == 0:
        return {}
    correct_cases = sum(1 for res in results if res["is_correct"])
    accuracy = correct_cases / total_cases * 100
    latency_ms = [res["metrics"].latency_ms for res in results]
    latency_mean = sum(latency_ms) / total_cases if latency_ms else 0
    tokens_total = sum([res["metrics"].total_tokens for res in results])
    tokens_prompt_total = sum([res["metrics"].prompt_tokens for res in results])
    tokens_completion_total = sum([res["metrics"].completion_tokens for res in results])

    return {
        "accuracy": accuracy,
        "latency_mean_ms": latency_mean,
        "tokens_total": tokens_total,
        "tokens_prompt_total": tokens_prompt_total,
        "tokens_completion_total": tokens_completion_total
    }, results
