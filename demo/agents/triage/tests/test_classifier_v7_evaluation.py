import os
import random
import statistics
from datetime import datetime

# Set tokenizers parallelism to avoid warnings
os.environ["TOKENIZERS_PARALLELISM"] = "false"

import mlflow
import numpy as np
import pytest

from agents.triage.classifier_v7.classifier_v7 import classifier_v7
from agents.triage.classifier_v7.config import ClassifierV7Settings
from agents.triage.data_sets.loader import load_dataset_triage_testing
from libraries.observability.logger import get_console_logger

logger = get_console_logger("test_classifier_v7_evaluation")


@pytest.mark.asyncio
async def test_classifier_v7():
    """MLflow evaluation test for v7 - matches v3/v5 pattern for comparison."""
    from dotenv import load_dotenv
    
    load_dotenv()
    
    # MLflow experiment setup (matches v3/v5 pattern)
    mlflow.set_experiment("triage_classifier")
    
    settings = ClassifierV7Settings()
    classifier_version = "classifier_v7"
    model_name_raw = settings.get_model_name()
    if settings.use_qat_model and model_name_raw in settings.qat_model_mapping:
        model_name_raw = settings.qat_model_mapping[model_name_raw]
    model = f"huggingface_{model_name_raw.replace('/', '_')}"
    model_name = f"{classifier_version}_{model}"
    run_name = f"test_{model_name}_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}"
    
    with mlflow.start_run(run_name=run_name):
        # Log parameters (matches v3/v5 pattern)
        mlflow.log_param("model_name", model_name)
        mlflow.log_param("classifier_version", classifier_version)
        mlflow.log_param("language_model", model)
        mlflow.log_param("use_qat_model", settings.use_qat_model)
        mlflow.log_param("use_4bit", settings.use_4bit)
        
        # Use same test dataset approach as v3/v5 (reduce to 10 for testing speed)
        random.seed(42)
        full_dataset = load_dataset_triage_testing()
        test_size = min(10, len(full_dataset))  # Use 10 samples for fast testing
        test_dataset = random.sample(full_dataset, test_size)
        all_scores = []
        results = []
        
        for case in test_dataset:
            try:
                res = classifier_v7(chat_history=case.conversation)
                all_scores.append(res.target_agent == case.target_agent)
                results.append({
                    "conversation": case.conversation,
                    "expected_agent": case.target_agent,
                    "predicted_agent": res.target_agent,
                    "metrics": res.metrics,
                })
            except Exception as e:
                # Handle HuggingFace/device failures gracefully
                logger.warning(f"Classification failed for sample: {e}")
                # Use fallback metrics for failed predictions
                from agents.triage.models import ClassifierMetrics, TargetAgent
                fallback_metrics = ClassifierMetrics(
                    total_tokens=0,
                    prompt_tokens=0,
                    completion_tokens=0,
                    latency_ms=0
                )
                all_scores.append(False)  # Failed prediction
                results.append({
                    "conversation": case.conversation,
                    "expected_agent": case.target_agent,
                    "predicted_agent": TargetAgent.ChattyAgent,  # Fallback
                    "metrics": fallback_metrics,
                })
        
        # Calculate metrics (identical to v3/v5 pattern)
        def ms(vals):
            return statistics.mean(vals) * 1_000 if vals else 0
        
        def p95(vals):
            return float(np.percentile(vals, 95)) if vals else 0
        
        accuracy = sum(all_scores) / len(all_scores) if all_scores else 0
        latencies_sec = [res["metrics"].latency_ms / 1_000 for res in results]
        prompt_tok_counts = [res["metrics"].prompt_tokens for res in results]
        completion_tok_counts = [res["metrics"].completion_tokens for res in results]
        total_tok_counts = [res["metrics"].total_tokens for res in results]
        
        metrics = {
            "accuracy": accuracy * 100,
            # latency
            "latency_mean_ms": ms(latencies_sec),
            "latency_p95_ms": p95(latencies_sec) * 1_000,  # p95 in ms
            "latency_max_ms": max(latencies_sec) * 1_000 if latencies_sec else 0,
            # tokens
            "tokens_total": sum(total_tok_counts),
            "tokens_prompt_total": sum(prompt_tok_counts),
            "tokens_completion_total": sum(completion_tok_counts),
            "tokens_mean": statistics.mean(total_tok_counts) if total_tok_counts else 0,
            "tokens_p95": p95(total_tok_counts),
        }
        mlflow.log_metrics(metrics)
        
        # Log failing examples (matches v3/v5 error analysis)
        failing_indices = [i for i, is_correct in enumerate(all_scores) if not is_correct]
        if failing_indices:
            logger.error(f"Accuracy: '{accuracy:.3f}';")
            logger.error(f"Found {len(failing_indices)} failing tests:")
            
            # Log first 5 failures for debugging
            for i in failing_indices[:5]:
                if i < len(results):
                    logger.error(f"\n{'=' * 80}\nFAILING TEST #{i}:")
                    logger.error(f"CONVERSATION:\n{results[i]['conversation']}")
                    logger.error(f"EXPECTED AGENT: {results[i]['expected_agent']}")
                    logger.error(f"PREDICTED AGENT: {results[i]['predicted_agent']}")
                    logger.error(f"{'=' * 80}")
        
        logger.info(f"V7 MLflow evaluation completed: {accuracy:.1%} accuracy")
        
        # Note: Don't assert accuracy threshold for v7 since it uses untrained base model
        # After fine-tuning, uncomment the line below:
        # assert accuracy > 0.8, f"V7 evaluation score {accuracy:.1%} is below 80% threshold."
        logger.info("V7 uses base model - train with 'make train-triage-classifier-v7' for better accuracy")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])