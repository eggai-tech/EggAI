#!/usr/bin/env python3
import logging
import os

from transformers import AutoModelForSequenceClassification, AutoTokenizer, AutoConfig

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


def train_finetune_model(train_sample_size: int, eval_sample_size: int, model_name: str) -> str:
    run_name = setup_mlflow_tracking(model_name)
    
    with mlflow.start_run(run_name=run_name):
        trainset = create_examples(train_sample_size, phase="train")
        logger.info(f"Loaded {len(trainset)} training examples")
        testset = create_examples(eval_sample_size, phase="test")
        logger.info(f"Loaded {len(testset)} test examples")

        log_training_parameters(train_sample_size, eval_sample_size, model_name, len(trainset), len(testset))
        
        if not model_name:
            model_name = v7_settings.get_model_name()

        logger.info(f"Using base model: {model_name}")

        perform_fine_tuning(trainset, testset)

        mlflow.log_artifacts(v7_settings.output_dir, artifact_path="model")
        # return artifact uri
        artifact_uri = mlflow.get_artifact_uri("model")
        logger.info(f"Model artifacts saved to: {artifact_uri}")
        return artifact_uri


if __name__ == "__main__":
    setup_logging()
    train_sample_size = int(os.getenv("FINETUNE_SAMPLE_SIZE", "-1"))
    eval_sample_size = int(os.getenv("EVALUATION_SAMPLE_SIZE", "-1"))
    logger.info(f"Training sample size: {train_sample_size}, Evaluation sample size: {eval_sample_size}")
    model_name = os.getenv("FINETUNE_BASE_MODEL", None)
    if model_name is None:
        model_name = v7_settings.get_model_name()
    show_training_info()
    
    artifact_uri = train_finetune_model(train_sample_size, eval_sample_size, model_name)
    local_path = mlflow.artifacts.download_artifacts(artifact_uri=artifact_uri)
    # Load the config and override num_labels
    config = AutoConfig.from_pretrained(model_name)
    config.num_labels = v7_settings.n_classes
    model = AutoModelForSequenceClassification.from_pretrained(local_path, config=config)
    tokenizer = AutoTokenizer.from_pretrained(local_path)

    triage_classifier = FinetunedClassifier(model=model, tokenizer=tokenizer)

    chat_history = "User: I want to know my policy due date."
    target_agent = triage_classifier.classify(chat_history=chat_history)
    logger.info(f"Predicted target agent: {target_agent} for chat:\n {chat_history}")

