import logging
import sys
import os

import mlflow
from dotenv import load_dotenv

from agents.triage.baseline_model.few_shots_classifier import FewShotsClassifier
from agents.triage.baseline_model.utils import load_datasets, init_mlflow, setup_logging
from agents.triage.baseline_model.config import settings

logger = logging.getLogger("fewshot_trainer")

load_dotenv()

def main() -> int:
    # Print current working directory
    logger.info(f"Current working directory: {os.getcwd()}")
    
    # Initialize MLflow
    init_mlflow(settings.mlflow_config_dict)

    # Load triage dataset
    logger.info(f"Loading dataset from {settings.dataset_paths}")
    dataset = load_datasets(settings.dataset_paths)

    if isinstance(settings.seed, int):
        seeds = [settings.seed]
    else:
        assert len(settings.seed) > 1
        seeds = settings.seed

    # Create few-shot classifier
    fewshot_classifier = FewShotsClassifier(
        n_classes=settings.n_classes,
        n_examples=settings.n_examples,
        seeds=seeds,
    )

    # Train the classifier
    logger.info(f"Training few-shot classifier with {settings.n_examples} examples")
    fewshot_classifier.fit(dataset)

    # Save the model locally
    logger.info(f"Saving classifier to {settings.checkpoint_dir}")
    model_path = fewshot_classifier.save(settings.checkpoint_dir, settings.model_name)

    # Save the model in the model registry
    logger.info(f"Saving model to MLflow model registry")
    mlflow.sklearn.log_model(
        sk_model=fewshot_classifier,
        artifact_path="model",
        registered_model_name=model_path.stem,
    )
    return 0


if __name__ == "__main__":
    setup_logging()
    sys.exit(main())
