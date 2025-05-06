import random
from datetime import datetime

import mlflow
import pytest

from agents.triage.baseline_model.classifier_v3 import classifier_v3
from agents.triage.data_sets.loader import load_dataset_triage_testing
from libraries.logger import get_console_logger

logger = get_console_logger("test_classifier_v3")


@pytest.mark.asyncio
async def test_classifier_v3():
    from dotenv import load_dotenv

    load_dotenv()

    mlflow.set_experiment("triage_classifier")
    with mlflow.start_run(
        run_name="test_classifier_v3_" + datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    ):
        mlflow.log_param("model_name", "classifier_v3")

        random.seed(42)
        test_dataset = random.sample(load_dataset_triage_testing(), 1000)
        all_scores = []
        results = []

        for case in test_dataset:
            res = classifier_v3(chat_history=case.conversation)
            all_scores.append(res.target_agent == case.target_agent)
            results.append(
                {
                    "conversation": case.conversation,
                    "expected_agent": case.target_agent,
                    "predicted_agent": res.target_agent,
                }
            )

        accuracy = sum(all_scores) / len(all_scores)

        failing_indices = [
            i for i, is_correct in enumerate(all_scores) if not is_correct
        ]
        if failing_indices:
            logger.error(f"Accuracy: '{accuracy}';")
            logger.error(f"Found {len(failing_indices)} failing tests:")

            for i in failing_indices:
                if i < len(results):
                    logger.error(f"\n{'=' * 80}\nFAILING TEST #{i}:")
                    logger.error(f"CONVERSATION:\n{results[i]['conversation']}")
                    logger.error(f"EXPECTED AGENT: {results[i]['expected_agent']}")
                    logger.error(f"PREDICTED AGENT: {results[i]['predicted_agent']}")
                    logger.error(f"{'=' * 80}")

        assert accuracy > 0.8, "Evaluation score is below threshold."
