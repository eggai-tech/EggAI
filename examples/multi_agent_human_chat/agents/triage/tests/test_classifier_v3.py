from datetime import datetime

import mlflow
import pytest

from ..baseline_model.classifier_v3 import classifier_v3
from ..dspy_modules.evaluation.evaluate import run_evaluation

@pytest.mark.asyncio
async def test_dspy_modules():
    from dotenv import load_dotenv
    load_dotenv()

    mlflow.set_experiment("triage_classifier")
    mlflow.start_run(run_name="test_classifier_v3_" + datetime.now().strftime("%Y-%m-%d_%H-%M-%S"))
    mlflow.log_param("model_name", "classifier_v3")

    score = run_evaluation(classifier_v3, "classifier_v3")
    assert score > 0.6, "Evaluation score is below threshold."