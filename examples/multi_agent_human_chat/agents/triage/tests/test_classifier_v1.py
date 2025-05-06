import types
from datetime import datetime

import mlflow
import pytest

from libraries.dspy_set_language_model import dspy_set_language_model
from agents.triage.dspy_modules.classifier_v1 import classifier_v1, settings
from agents.triage.dspy_modules.evaluation.evaluate import run_evaluation
from libraries.logger import get_console_logger

logger = get_console_logger("test_classifier_v1")

lm = dspy_set_language_model(types.SimpleNamespace(
    language_model=settings.language_model,
    cache_enabled=True,
    language_model_api_base=settings.language_model_api_base,
))


@pytest.mark.asyncio
async def test_dspy_modules():
    from dotenv import load_dotenv
    load_dotenv()

    mlflow.dspy.autolog(
        log_compiles=True,
        log_traces=True,
        log_evals=True,
        log_traces_from_compile=True,
        log_traces_from_eval=True
    )

    mlflow.set_experiment("triage_classifier")
    with mlflow.start_run(run_name="test_classifier_v1_" + datetime.now().strftime("%Y-%m-%d_%H-%M-%S")):
        mlflow.log_param("model_name", "classifier_v1")

        accuracy, results, all_scores, metrics = run_evaluation(classifier_v1, "classifier_v1", lm)
        
        failing_indices = [i for i, is_correct in enumerate(all_scores) if not is_correct]
        if failing_indices:
            logger.error(f"Accuracy: '{accuracy}'; Metrics: '{metrics}'")
            logger.error(f"Found {len(failing_indices)} failing tests:")
            
            for i in failing_indices:
                if i < len(results):
                    example, prediction, _ = results[i]
                    logger.error(f"\n{'='*80}\nFAILING TEST #{i}:")
                    logger.error(f"CONVERSATION:\n{example.chat_history}")
                    logger.error(f"EXPECTED AGENT: {example.target_agent.value}")
                    logger.error(f"PREDICTED AGENT: {str(prediction)}")
                    logger.error(f"{'='*80}")

        assert accuracy > 0.8, "Evaluation score is below threshold."
