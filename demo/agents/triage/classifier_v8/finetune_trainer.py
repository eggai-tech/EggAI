#!/usr/bin/env python3
import logging
import os
import shutil

import mlflow
from dotenv import load_dotenv

from agents.triage.baseline_model.utils import setup_logging
from agents.triage.classifier_v7.training_utils import setup_mlflow_tracking
from agents.triage.classifier_v8.config import ClassifierV8Settings
from agents.triage.classifier_v8.training_utils import (
    log_training_parameters,
    perform_fine_tuning,
    show_training_info,
)
from agents.triage.shared.data_utils import create_examples

os.environ["TOKENIZERS_PARALLELISM"] = "false"
load_dotenv()
v8_settings = ClassifierV8Settings()

logger = logging.getLogger(__name__)


def train_finetune_model() -> str:
    model_name = v8_settings.model_name
    run_name = setup_mlflow_tracking(model_name)
    
    with mlflow.start_run(run_name=run_name):
        current_exp = mlflow.get_experiment(mlflow.active_run().info.experiment_id)
        logger.info(f"Active experiment: {current_exp.name} (ID: {current_exp.experiment_id})")

        train_sample_size = v8_settings.train_sample_size
        trainset = create_examples(train_sample_size, phase="train")
        logger.info(f"Loaded {len(trainset)} training examples")
        
        eval_sample_size = v8_settings.eval_sample_size
        testset = create_examples(eval_sample_size, phase="test")
        logger.info(f"Loaded {len(testset)} test examples")

        log_training_parameters()

        logger.info(f"Using base model: {model_name}")
        
        perform_fine_tuning(trainset, testset)

        output_dir = v8_settings.output_dir
        for item in os.listdir(output_dir):
            if item.startswith("checkpoint"):
                item_path = os.path.join(output_dir, item)
                if os.path.isdir(item_path):
                    logger.info(f"Removing old checkpoint directory: {item_path}")
                    shutil.rmtree(item_path)

        mlflow.log_artifacts(v8_settings.output_dir, artifact_path="model")

        run_id = mlflow.active_run().info.run_id
        model_uri = f"runs:/{run_id}/model"
        logger.info(f"Model URI: {model_uri}")
        return model_uri


if __name__ == "__main__":
    setup_logging()
    show_training_info()
    
    model_uri = train_finetune_model()
    logger.info(f"Fine-tuned LoRA model saved to mlflow. URI: {model_uri}")
    logger.info("RoBERTa LoRA training and MLflow logging completed successfully!")