from datetime import datetime

import mlflow
import pytest

from ..dspy_modules.classifier_v1 import classifier_v1
from ..dspy_modules.classifier_v2.classifier_v2 import classifier_v2
from ..dspy_modules.evaluation.evaluate import run_evaluation

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
    mlflow.start_run(run_name="test_classifier_v2_" + datetime.now().strftime("%Y-%m-%d_%H-%M-%S"))
    mlflow.log_param("model_name", "classifier_v2")

    score = run_evaluation(classifier_v2, "classifier_v2")
    assert score > 0.6, "Evaluation score is below threshold."