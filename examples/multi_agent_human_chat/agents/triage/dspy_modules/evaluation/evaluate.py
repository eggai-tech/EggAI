import os
import random
import statistics
import time
import types

import dspy
import mlflow
import numpy as np
from dotenv import load_dotenv

from agents.triage.data_sets.loader import load_dataset_triage_testing, as_dspy_examples
from agents.triage.dspy_modules.classifier_v1 import classifier_v1
from agents.triage.dspy_modules.evaluation.report import generate_report
from libraries.dspy_set_language_model import dspy_set_language_model
import csv
from libraries.logger import get_console_logger
from agents.triage.config import Settings

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
            dataset.append({
                "conversation": conversation,
                "target": target
            })

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
    random.seed(42)
    test_dataset = random.sample(as_dspy_examples(load_dataset_triage_testing()), 1000)
    evaluator = dspy.evaluate.Evaluate(
        devset=test_dataset,
        num_threads=20,
        display_progress=True,
        return_outputs=True,
        return_all_scores=True
    )

    latencies_sec: list[float] = []
    prompt_tok_counts: list[int] = []
    completion_tok_counts: list[int] = []
    total_tok_counts: list[int] = []

    def timed_program(**kwargs):
        start = time.perf_counter()
        pred = program(**kwargs)  # your original module call
        latencies_sec.append(time.perf_counter() - start)

        prompt_tok_counts.append(lm.prompt_tokens)
        completion_tok_counts.append(lm.completion_tokens)
        total_tok_counts.append(lm.total_tokens)

        return pred

    evaluator = dspy.evaluate.Evaluate(
        devset=test_dataset,
        num_threads=10,
        display_progress=True,
        return_outputs=True,
        return_all_scores=True
    )

    accuracy, results, all_scores = evaluator(
        timed_program,
        metric=lambda ex, pred, trace=None:
        ex.target_agent.lower() == pred.target_agent.lower()
    )

    def ms(vals):   return statistics.mean(vals) * 1_000

    def p95(vals):  return float(np.percentile(vals, 95))

    metrics = {
        "accuracy": accuracy,
        # latency
        "latency_mean_ms": ms(latencies_sec),
        "latency_p95_ms": ms(latencies_sec) * 0 + p95(latencies_sec) * 1_000,  # p95 in ms
        "latency_max_ms": max(latencies_sec) * 1_000,
        # tokens
        "tokens_total": sum(total_tok_counts),
        "tokens_prompt_total": sum(prompt_tok_counts),
        "tokens_completion_total": sum(completion_tok_counts),
        "tokens_mean": statistics.mean(total_tok_counts),
        "tokens_p95": p95(total_tok_counts),
    }
    mlflow.log_metrics(metrics)

    generate_report(results, report_name)

    return accuracy, results, all_scores, metrics


if __name__ == "__main__":
    current_language_model = dspy_set_language_model(types.SimpleNamespace(
        language_model=settings.language_model,
        cache_enabled=True,
        language_model_api_base=settings.language_model_api_base,
    ))
    sc = run_evaluation(classifier_v1, "classifier_v1", current_language_model)
    logger.info(f"Accuracy: {sc}")
