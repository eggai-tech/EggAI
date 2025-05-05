import types
from datetime import datetime

import mlflow
import pytest

from agents.triage.config import Settings
from libraries.dspy_set_language_model import dspy_set_language_model
from agents.triage.dspy_modules.classifier_v1 import classifier_v1, settings
from agents.triage.dspy_modules.evaluation.evaluate import run_evaluation

settings = Settings()

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
        assert accuracy > 0.8, "Evaluation score is below threshold."
