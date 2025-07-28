import os
import random
import statistics
from datetime import datetime

# Set tokenizers parallelism to avoid warnings
os.environ["TOKENIZERS_PARALLELISM"] = "false"

import mlflow
import numpy as np
import pytest

from agents.triage.baseline_model.classifier_v3 import classifier_v3, settings
from agents.triage.data_sets.loader import load_dataset_triage_testing
from libraries.observability.logger import get_console_logger

logger = get_console_logger("test_classifier_v3")


@pytest.mark.asyncio
async def test_classifier_v3():
    from dotenv import load_dotenv

    load_dotenv()

    mlflow.set_experiment("triage_classifier")

    classifier_version = "classifier_v3"
    model = (
        f"{settings.classifier_v3_model_name}_{settings.classifier_v3_model_version}"
    )
    model_name = f"{classifier_version}_{model}"
    run_name = f"test_{model_name}_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}"

    with mlflow.start_run(run_name=run_name):
        mlflow.log_param("model_name", model_name)
        mlflow.log_param("classifier_version", classifier_version)
        mlflow.log_param("language_model", model)

        random.seed(42)
        test_dataset = random.sample(load_dataset_triage_testing(), 1000)
        all_scores = []
        results = []

        for case in test_dataset:
            res = classifier_v3(chat_history=case.conversation)
            all_scores.append(res.target_agent == case.target_agent)
            results.append(
                {
                    "conversation": case.conversation,
                    "expected_agent": case.target_agent,
                    "predicted_agent": res.target_agent,
                    "metrics": res.metrics,
                }
            )

        # log the metrics on mlflow
        def ms(vals):
            return statistics.mean(vals) * 1_000

        def p95(vals):
            return float(np.percentile(vals, 95))

        accuracy = sum(all_scores) / len(all_scores)
        latencies_sec = [res["metrics"].latency_ms / 1_000 for res in results]
        prompt_tok_counts = [res["metrics"].prompt_tokens for res in results]
        completion_tok_counts = [res["metrics"].completion_tokens for res in results]
        total_tok_counts = [res["metrics"].total_tokens for res in results]

        metrics = {
            "accuracy": accuracy * 100,
            # latency
            "latency_mean_ms": ms(latencies_sec),
            "latency_p95_ms": ms(latencies_sec) * 0
            + p95(latencies_sec) * 1_000,  # p95 in ms
            "latency_max_ms": max(latencies_sec) * 1_000,
            # tokens
            "tokens_total": sum(total_tok_counts),
            "tokens_prompt_total": sum(prompt_tok_counts),
            "tokens_completion_total": sum(completion_tok_counts),
            "tokens_mean": statistics.mean(total_tok_counts),
            "tokens_p95": p95(total_tok_counts),
        }
        mlflow.log_metrics(metrics)

        accuracy = sum(all_scores) / len(all_scores)

        failing_indices = [
            i for i, is_correct in enumerate(all_scores) if not is_correct
        ]
        if failing_indices:
            logger.error(f"Accuracy: '{accuracy}';")
            logger.error(f"Found {len(failing_indices)} failing tests:")

            for i in failing_indices:
                if i < len(results):
                    logger.error(f"\n{'=' * 80}\nFAILING TEST #{i}:")
                    logger.error(f"CONVERSATION:\n{results[i]['conversation']}")
                    logger.error(f"EXPECTED AGENT: {results[i]['expected_agent']}")
                    logger.error(f"PREDICTED AGENT: {results[i]['predicted_agent']}")
                    logger.error(f"{'=' * 80}")

        assert accuracy > 0.8, "Evaluation score is below threshold."
