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

logger = get_console_logger("test_classifier_v7")


@pytest.mark.asyncio
async def test_classifier_v7():
    from dotenv import load_dotenv

    load_dotenv()
    v7_settings = ClassifierV7Settings()

    # Skip test if HuggingFace model is not available (no API endpoint to check)
    # Just proceed with the test
    logger.info("Testing HuggingFace Gemma classifier v7")

    # Enable DSPy autologging
    mlflow.dspy.autolog(
        log_compiles=True,
        log_traces=True,
        log_evals=True,
        log_traces_from_compile=True,
        log_traces_from_eval=True,
    )

    mlflow.set_experiment("triage_classifier")

    classifier_version = "classifier_v7"
    model_id = v7_settings.get_model_name()
    model_name = f"{classifier_version}_{model_id.replace('/', '_') if model_id else 'unknown'}"
    run_name = f"test_{model_name}_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}"

    with mlflow.start_run(run_name=run_name):
        mlflow.log_param("model_name", model_name)
        mlflow.log_param("classifier_version", classifier_version)
        mlflow.log_param("base_model_id", model_id)

        # Use a smaller sample for testing
        test_sample_size = min(100, len(load_dataset_triage_testing()))
        random.seed(42)
        test_dataset = random.sample(load_dataset_triage_testing(), test_sample_size)
        all_scores = []
        results = []

        logger.info(f"Testing classifier_v7 with {len(test_dataset)} examples")

        for i, case in enumerate(test_dataset):
            try:
                res = classifier_v7(chat_history=case.conversation)
                is_correct = res.target_agent == case.target_agent
                all_scores.append(is_correct)
                results.append(
                    {
                        "conversation": case.conversation,
                        "expected_agent": case.target_agent,
                        "predicted_agent": res.target_agent,
                        "metrics": res.metrics,
                        "correct": is_correct,
                    }
                )
                
                if i % 10 == 0:
                    logger.info(f"Processed {i + 1}/{len(test_dataset)} examples")
                    
            except Exception as e:
                logger.error(f"Failed to classify example {i}: {e}")
                # Count as incorrect
                all_scores.append(False)
                results.append(
                    {
                        "conversation": case.conversation,
                        "expected_agent": case.target_agent,
                        "predicted_agent": "ERROR",
                        "metrics": None,
                        "correct": False,
                        "error": str(e),
                    }
                )

        # Calculate and log metrics
        def ms(vals):
            return statistics.mean(vals) * 1_000 if vals else 0

        def p95(vals):
            return float(np.percentile(vals, 95)) if vals else 0

        accuracy = sum(all_scores) / len(all_scores) if all_scores else 0
        
        # Filter out results with errors for token metrics
        valid_results = [res for res in results if res["metrics"] is not None]
        
        if valid_results:
            latencies_sec = [res["metrics"].latency_ms / 1_000 for res in valid_results]
            prompt_tok_counts = [res["metrics"].prompt_tokens for res in valid_results]
            completion_tok_counts = [res["metrics"].completion_tokens for res in valid_results]
            total_tok_counts = [res["metrics"].total_tokens for res in valid_results]
        else:
            latencies_sec = prompt_tok_counts = completion_tok_counts = total_tok_counts = []

        metrics = {
            "accuracy": accuracy * 100,
            "total_examples": len(test_dataset),
            "valid_predictions": len(valid_results),
            "error_count": len(test_dataset) - len(valid_results),
            # latency
            "latency_mean_ms": ms(latencies_sec),
            "latency_p95_ms": p95(latencies_sec) * 1_000 if latencies_sec else 0,
            "latency_max_ms": max(latencies_sec) * 1_000 if latencies_sec else 0,
            # tokens
            "tokens_total": sum(total_tok_counts),
            "tokens_prompt_total": sum(prompt_tok_counts),
            "tokens_completion_total": sum(completion_tok_counts),
            "tokens_mean": statistics.mean(total_tok_counts) if total_tok_counts else 0,
            "tokens_p95": p95(total_tok_counts),
        }
        mlflow.log_metrics(metrics)

        logger.info(f"Final accuracy: {accuracy:.3f} ({accuracy * 100:.1f}%)")
        logger.info(f"Valid predictions: {len(valid_results)}/{len(test_dataset)}")

        # Log failing examples for debugging
        failing_indices = [
            i for i, is_correct in enumerate(all_scores) if not is_correct
        ]
        if failing_indices:
            logger.error(f"Found {len(failing_indices)} failing tests:")

            # Log first few failures for debugging
            for i in failing_indices[:5]:  # Limit to first 5 failures
                if i < len(results):
                    logger.error(f"\n{'=' * 80}\nFAILING TEST #{i}:")
                    logger.error(f"CONVERSATION:\n{results[i]['conversation']}")
                    logger.error(f"EXPECTED AGENT: {results[i]['expected_agent']}")
                    logger.error(f"PREDICTED AGENT: {results[i]['predicted_agent']}")
                    if 'error' in results[i]:
                        logger.error(f"ERROR: {results[i]['error']}")
                    logger.error(f"{'=' * 80}")

        # More lenient threshold for local fine-tuned model
        min_accuracy = 0.50  # 50% minimum accuracy (lower than v6 due to local training)
        assert accuracy > min_accuracy, f"Evaluation score {accuracy:.3f} is below threshold {min_accuracy}"


def test_classifier_v7_configuration():
    from agents.triage.classifier_v7.config import ClassifierV7Settings
    
    v7_config = ClassifierV7Settings()
    
    # Check configuration is valid
    assert v7_config.model_name is not None, "Model not configured"
    assert 'gemma' in v7_config.model_name.lower(), f"Model {v7_config.model_name} is not a Gemma model"
    
    # Test import
    try:
        from agents.triage.classifier_v7.classifier_v7 import (
            classifier_v7,  # noqa: F401
        )
    except ImportError as e:
        pytest.fail(f"Classifier import failed: {e}")


@pytest.mark.asyncio 
async def test_classifier_v7_basic():
    from dotenv import load_dotenv

    load_dotenv()
    v7_settings = ClassifierV7Settings()

    # Skip test if HuggingFace model is not available (no API endpoint to check)
    # Just proceed with the test
    logger.info("Testing HuggingFace Gemma classifier v7 basic functionality")

    # Test basic classification functionality
    test_cases = [
        ("User: I need help with my insurance claim", "ClaimsAgent"),
        ("User: What's my policy coverage?", "PolicyAgent"),
        ("User: I need to pay my bill", "BillingAgent"),
        ("User: Hello, how are you?", "ChattyAgent"),
    ]

    for chat_history, expected_category in test_cases:
        result = classifier_v7(chat_history=chat_history)
        
        # Check that we get a valid response
        assert result is not None
        assert hasattr(result, 'target_agent')
        assert hasattr(result, 'metrics')
        
        # Check that metrics are populated
        assert result.metrics is not None
        assert result.metrics.latency_ms >= 0
        
        logger.info(f"Input: {chat_history}")
        logger.info(f"Predicted: {result.target_agent}, Expected category: {expected_category}")
        logger.info(f"Latency: {result.metrics.latency_ms:.2f}ms")
        logger.info("---")


if __name__ == "__main__":
    import asyncio
    
    async def run_tests():
        await test_classifier_v7_basic()
        await test_classifier_v7()
    
    asyncio.run(run_tests())