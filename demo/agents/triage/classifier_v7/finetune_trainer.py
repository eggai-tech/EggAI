#!/usr/bin/env python3
import logging
import os

from mlflow.models import infer_signature

from agents.triage.baseline_model.utils import setup_logging
from agents.triage.classifier_v7.classifier_v7 import FinetunedClassifier
from agents.triage.data_sets.loader import AGENT_TO_LABEL, translate_agent_str_to_enum
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
        trainset = create_examples(sample_size, phase="train")
        logger.info(f"Loaded {len(trainset)} training examples")
        # load the whole test set for evaluation
        testset = create_examples(-1, phase="test")
        logger.info(f"Loaded {len(testset)} test examples")

        log_training_parameters(sample_size, model_name, len(trainset), len(testset))
        
        if not model_name:
            model_name = v7_settings.get_model_name()

        logger.info(f"Using base model: {model_name}")

        model, tokenizer = perform_fine_tuning(trainset, testset)

        # save the fine-tuned transformer model to mlflow
        sample = trainset[0]
        signature = infer_signature(
            model_input=sample["chat_history"],
            model_output=AGENT_TO_LABEL[translate_agent_str_to_enum(sample["target_agent"])],
        )
        mlflow.transformers.log_model(
            transformers_model={"model": model, "tokenizer": tokenizer},
            signature=signature,
            name="model",  # relative path to save model files within MLflow run
        )

        # return model uri
        run_id = mlflow.active_run().info.run_id
        model_uri = f"runs:/{run_id}/model"
        logger.info(f"Model URI: {model_uri}")
        return model_uri


if __name__ == "__main__":
    setup_logging()
    sample_size = int(os.getenv("FINETUNE_SAMPLE_SIZE", "-1"))
    model_name = os.getenv("FINETUNE_BASE_MODEL", None)
    if model_name is None:
        model_name = v7_settings.get_model_name()
    show_training_info()
    
    model_uri = train_finetune_model(sample_size, model_name)
    logger.info(f"Fine-tuned model saved to mlflow. URI: {model_uri}")

    # test the model on a sample chat history
    logger.info(f"Loading fine-tuned model from URI: {model_uri} for testing...")
    model_dict = mlflow.transformers.load_model(model_uri, return_type="components")
    triage_classifier = FinetunedClassifier(**model_dict)

    chat_history = "User: I want to know my policy due date."
    target_agent = triage_classifier.classify(chat_history=chat_history)
    logger.info(f"Predicted target agent: {target_agent} for chat:\n {chat_history}")

