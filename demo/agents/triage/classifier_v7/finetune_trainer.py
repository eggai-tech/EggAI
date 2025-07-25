#!/usr/bin/env python3
import logging
import os

from agents.triage.baseline_model.utils import setup_logging
from agents.triage.classifier_v7.classifier_v7 import FinetunedClassifier
from agents.triage.shared.data_utils import create_examples

# Set tokenizers parallelism to avoid warnings
os.environ["TOKENIZERS_PARALLELISM"] = "false"

import mlflow
from dotenv import load_dotenv

from agents.triage.classifier_v7.config import ClassifierV7Settings
from agents.triage.classifier_v7.training_utils import (
    log_training_parameters,
    perform_fine_tuning,
    setup_mlflow_tracking,
    show_training_info,
)

load_dotenv()
v7_settings = ClassifierV7Settings()

os.environ["DSPY_CACHEDIR"] = "./dspy_cache"
logger = logging.getLogger(__name__)


def train_finetune_model(sample_size: int, model_name: str) -> str:
    run_name = setup_mlflow_tracking(model_name)
    
    with mlflow.start_run(run_name=run_name):
        # Verify we're in the correct experiment
        current_exp = mlflow.get_experiment(mlflow.active_run().info.experiment_id)
        logger.info(f"Active experiment: {current_exp.name} (ID: {current_exp.experiment_id})")
        
        trainset = create_examples(sample_size, phase="train")
        logger.info(f"Loaded {len(trainset)} training examples")
        # load test set for evaluation (configurable size)
        eval_sample_size = int(os.getenv("EVALUATION_SAMPLE_SIZE", "-1"))
        testset = create_examples(eval_sample_size, phase="test")
        logger.info(f"Loaded {len(testset)} test examples")

        log_training_parameters(sample_size, eval_sample_size, model_name, len(trainset), len(testset))
        
        if not model_name:
            model_name = v7_settings.get_model_name()

        logger.info(f"Using base model: {model_name}")
        
        best_model, tokenizer = perform_fine_tuning(trainset, testset)

        # perform a sanity check on the model
        finetuned_classifier = FinetunedClassifier(model=best_model, tokenizer=tokenizer)
        chat_history = "User: I want to know my policy due date."
        test_result = finetuned_classifier.classify(chat_history)
        logger.info(f"Chat history: {chat_history}. Target agent: {test_result.target_agent}")

        # TODO: save the best model to MLflow
        # Return model uri from the primary artifacts
        run_id = mlflow.active_run().info.run_id
        model_uri = f"runs:/{run_id}/model"
        logger.info(f"Model URI: {model_uri}")
        return model_uri


if __name__ == "__main__":
    setup_logging()
    sample_size = int(os.getenv("FINETUNE_SAMPLE_SIZE", "-1"))
    eval_sample_size = int(os.getenv("EVALUATION_SAMPLE_SIZE", "-1"))
    logger.info(f"Training sample size: {sample_size}, Evaluation sample size: {eval_sample_size}")
    model_name = os.getenv("FINETUNE_BASE_MODEL", None)
    if model_name is None:
        model_name = v7_settings.get_model_name()
    show_training_info()
    
    model_uri = train_finetune_model(sample_size, model_name)
    logger.info(f"Fine-tuned model saved to mlflow. URI: {model_uri}")
    logger.info("Training and MLflow logging completed successfully!")

