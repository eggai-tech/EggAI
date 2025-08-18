import logging
import os
import shutil
from datetime import datetime

import mlflow
from dotenv import load_dotenv

from agents.triage.baseline_model.utils import setup_logging
from agents.triage.classifier_v8.classifier_v8 import FinetunedRobertaClassifier
from agents.triage.classifier_v8.config import ClassifierV8Settings
from agents.triage.data_sets.loader import load_dataset_triage_testing
from agents.triage.shared.triage_eval import evaluate_classifier

# Initialize logging first
setup_logging()
logger = logging.getLogger(__name__)

load_dotenv()
v8_settings = ClassifierV8Settings()


def eval_classifier_v8(model_path: str):
    """Test set evaluation for Classifier V8 using MLflow tracking."""

    # MLflow experiment setup
    mlflow.set_experiment("triage_classifier_eval")

    classifier_version = "classifier_v8"
    model_name = v8_settings.model_name
    run_name = f"{model_name}-ft-{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}"

    with mlflow.start_run(run_name=run_name):
        # Log parameters
        mlflow.log_param("model_name", f"{classifier_version}_{model_name}")
        mlflow.log_param("classifier_version", classifier_version)
        mlflow.log_param("base_model", model_name)


        # load dataset
        full_dataset = load_dataset_triage_testing()
        logger.info(f"Loaded {len(full_dataset)} test examples from the dataset.")

        # load FinetunedRobertaClassifier
        classifier = FinetunedRobertaClassifier(model_path=model_path)
        logger.info(f"Loaded classifier from: {model_path}")

        logger.info(f"Starting evaluation for {classifier_version} with fine-tuned model: {model_name}")
        # evaluate on test set
        metrics, detailed_results = evaluate_classifier(classifier, full_dataset)

        mlflow.log_metrics(metrics)

        # Log failing examples for error analysis
        for i, result in enumerate(detailed_results):
            if not result["is_correct"]:
                logger.info(f"Failing example {i}: {result['conversation']}")
                logger.info(f"Expected: {result['expected_agent']}, Predicted: {result['predicted_agent']}")

        logger.info(f"V8 MLflow evaluation completed: {metrics['accuracy']} accuracy")


if __name__ == "__main__":
    # get artifact URI from environment variable if available
    run_id = os.getenv("TRIAGE_V8_RUN_ID", None)

    if run_id is not None:
        logger.info(f"Using MLflow artifact from run id: {run_id}")
        model_path = mlflow.artifacts.download_artifacts(run_id=run_id, artifact_path="model")
        logger.info(f"Downloaded model to: {model_path}")
        should_cleanup = True
    else:
        logger.warning("No TRIAGE_V8_RUN_ID provided, using local model.")
        model_path = v8_settings.output_dir
        logger.info(f"Using local model directory: {model_path}")
        should_cleanup = False

    eval_classifier_v8(model_path=model_path)

    if should_cleanup:
        logger.info(f"Cleaning up downloaded model directory: {model_path}")
        shutil.rmtree(model_path, ignore_errors=True)
        logger.info("Cleanup completed.")
