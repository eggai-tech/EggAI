import csv
import os
import random
import statistics
import time
import types

import dspy
import mlflow
import numpy as np
from dotenv import load_dotenv

from agents.triage.config import Settings
from agents.triage.data_sets.loader import as_dspy_examples, load_dataset_triage_testing
from agents.triage.dspy_modules.classifier_v1 import classifier_v1
from agents.triage.dspy_modules.evaluation.report import generate_report
from libraries.ml.dspy.language_model import dspy_set_language_model
from libraries.observability.logger import get_console_logger

settings = Settings()

load_dotenv()
logger = get_console_logger("triage_agent.dspy_modules")


def load_dataset(filename: str) -> list:
    csv_file_path = os.path.abspath(
        os.path.join(os.path.dirname(__file__), f"{filename}.csv")
    )
    dataset = []

    with open(csv_file_path, "r", newline="", encoding="utf-8") as csvfile:
        reader = csv.DictReader(csvfile)
        next(reader, None)
        for row in reader:
            conversation = row["conversation"].replace("\\n", "\n").replace('"', "")
            target = row["target"].replace("\\n", "\n").replace('"', "")
            dataset.append({"conversation": conversation, "target": target})

    return dataset


def load_data(file: str):
    devset = []
    for ex in load_dataset(file):
        devset.append(
            dspy.Example(
                chat_history=ex["conversation"],
                target_agent=ex["target"],
            ).with_inputs("chat_history")
        )
    return devset


def run_evaluation(program, report_name, lm: dspy.LM):
    # Print language model info for debugging
    logger.info(f"Using language model: {settings.language_model}")

    full_test_dataset = as_dspy_examples(load_dataset_triage_testing())

    # Limit dataset size for testing based on settings
    test_dataset_size = min(settings.test_dataset_size, len(full_test_dataset))

    # If test_dataset_size is set to a value, use a subset of the test dataset
    if test_dataset_size < len(full_test_dataset):
        # Use seed for reproducibility
        random.seed(42)
        test_dataset = random.sample(full_test_dataset, test_dataset_size)
        logger.info(
            f"Using {test_dataset_size} examples for testing (from total {len(full_test_dataset)})"
        )
    else:
        test_dataset = full_test_dataset
        logger.info(f"Using all {len(full_test_dataset)} examples for testing")

    evaluator = dspy.evaluate.Evaluate(
        devset=test_dataset,
        num_threads=8,
        display_progress=True,
        return_outputs=True,
        return_all_scores=True,
    )

    latencies_sec: list[float] = []
    prompt_tok_counts: list[int] = []
    completion_tok_counts: list[int] = []
    total_tok_counts: list[int] = []

    def timed_program(**kwargs):
        start = time.perf_counter()
        lm.start_run()  # Reset token counts before each call
        pred = program(**kwargs)  # your original module call
        latencies_sec.append(time.perf_counter() - start)

        # Get token counts from LM
        prompt_tok_counts.append(lm.prompt_tokens)
        completion_tok_counts.append(lm.completion_tokens)
        total_tok_counts.append(lm.total_tokens)

        # Also record token counts in prediction metrics if possible
        if hasattr(pred, "metrics"):
            pred.metrics.prompt_tokens = lm.prompt_tokens
            pred.metrics.completion_tokens = lm.completion_tokens
            pred.metrics.total_tokens = lm.total_tokens
            pred.metrics.latency_ms = (time.perf_counter() - start) * 1000

        # Debug logging
        if os.environ.get("TRIAGE_DEBUG_EVAL") == "1":
            logger.debug(
                f"Tokens - P:{lm.prompt_tokens}, C:{lm.completion_tokens}, T:{lm.total_tokens}"
            )

        return pred

    accuracy, results, all_scores = evaluator(
        timed_program,
        metric=lambda ex, pred, trace=None: ex.target_agent.lower()
        == pred.target_agent.lower(),
    )

    def ms(vals):
        return statistics.mean(vals) * 1_000

    def p95(vals):
        return float(np.percentile(vals, 95))

    metrics = {
        "accuracy": accuracy,
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
        # per example
        "tokens_per_example": sum(total_tok_counts) / len(total_tok_counts),
        "prompt_tokens_per_example": sum(prompt_tok_counts) / len(prompt_tok_counts),
        "completion_tokens_per_example": sum(completion_tok_counts)
        / len(completion_tok_counts),
    }

    # Log summary metrics for easy comparison
    logger.info("\n" + "=" * 80)
    logger.info(f"CLASSIFIER PERFORMANCE SUMMARY: {report_name}")
    logger.info(f"Accuracy: {accuracy:.2f}%")
    logger.info(f"Avg Latency: {ms(latencies_sec):.2f}ms")
    logger.info(
        f"Avg Total Tokens: {sum(total_tok_counts) / len(total_tok_counts):.1f}"
    )
    logger.info(
        f"Avg Prompt Tokens: {sum(prompt_tok_counts) / len(prompt_tok_counts):.1f}"
    )
    logger.info(
        f"Avg Completion Tokens: {sum(completion_tok_counts) / len(completion_tok_counts):.1f}"
    )
    logger.info(f"Examples tested: {len(test_dataset)}")
    logger.info("=" * 80 + "\n")

    # Log to MLflow
    mlflow.log_metrics(metrics)

    generate_report(results, report_name)

    return accuracy, results, all_scores, metrics


if __name__ == "__main__":
    current_language_model = dspy_set_language_model(
        types.SimpleNamespace(
            language_model=settings.language_model,
            cache_enabled=True,
            language_model_api_base=settings.language_model_api_base,
        )
    )
    sc = run_evaluation(classifier_v1, "classifier_v1", current_language_model)
    logger.info(f"Accuracy: {sc}")
