import random
from datetime import datetime

import mlflow
import pytest

from ..baseline_model.classifier_v3 import classifier_v3
from ..data_sets.loader import load_dataset_triage_testing

@pytest.mark.asyncio
async def test_classifier_v3():
    from dotenv import load_dotenv
    load_dotenv()

    mlflow.set_experiment("triage_classifier")
    mlflow.start_run(run_name="test_classifier_v3_" + datetime.now().strftime("%Y-%m-%d_%H-%M-%S"))
    mlflow.log_param("model_name", "classifier_v3")

    random.seed(42)
    test_dataset = random.sample(load_dataset_triage_testing(), 1000)
    accuracies = []

    for case in test_dataset:
        res = classifier_v3(
            chat_history=case.conversation
        )
        accuracies.append(res.target_agent == case.target_agent)

    accuracy = sum(accuracies) / len(accuracies)
    assert accuracy > 0.8, "Evaluation score is below threshold."