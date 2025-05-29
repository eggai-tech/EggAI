import types
from datetime import datetime

import mlflow
import pytest

from libraries.dspy_set_language_model import dspy_set_language_model
from libraries.logger import get_console_logger

from ..dspy_modules.classifier_v2.classifier_v2 import classifier_v2, settings
from ..dspy_modules.evaluation.evaluate import run_evaluation

logger = get_console_logger("test_classifier_v2")

lm = dspy_set_language_model(
    types.SimpleNamespace(
        language_model=settings.language_model,
        cache_enabled=False,  # Disable cache for tests to get accurate token counts
        language_model_api_base=settings.language_model_api_base,
    )
)


@pytest.mark.asyncio
async def test_dspy_modules():
    from dotenv import load_dotenv

    load_dotenv()

    mlflow.dspy.autolog(
        log_compiles=True,
        log_traces=True,
        log_evals=True,
        log_traces_from_compile=True,
        log_traces_from_eval=True,
    )

    mlflow.set_experiment("triage_classifier")

    classifier_version = "classifier_v2"
    model_name = f"{classifier_version}_{settings.language_model}"
    run_name = f"test_{model_name}_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}"

    with mlflow.start_run(run_name=run_name):
        mlflow.log_param("model_name", model_name)
        mlflow.log_param("classifier_version", classifier_version)
        mlflow.log_param("language_model", settings.language_model)

        accuracy, results, all_scores, metrics = run_evaluation(
            classifier_v2, classifier_version, lm
        )

        failing_indices = [
            i for i, is_correct in enumerate(all_scores) if not is_correct
        ]
        if failing_indices:
            logger.error(f"Accuracy: '{accuracy}'; Metrics: '{metrics}'")
            logger.error(f"Found {len(failing_indices)} failing tests:")

            for i in failing_indices:
                if i < len(results):
                    example, prediction, _ = results[i]
                    logger.error(f"\n{'=' * 80}\nFAILING TEST #{i}:")
                    logger.error(f"CONVERSATION:\n{example.chat_history}")
                    logger.error(f"EXPECTED AGENT: {example.target_agent.value}")
                    logger.error(f"PREDICTED AGENT: {str(prediction)}")
                    logger.error(f"{'=' * 80}")

        assert accuracy > 0.9, "Evaluation score is below threshold."
