#!/usr/bin/env python3
import logging
import os

from agents.triage.baseline_model.utils import setup_logging
from agents.triage.classifier_v7.classifier_v7 import FinetunedClassifier
from agents.triage.data_sets.loader import AGENT_TO_LABEL
from agents.triage.shared.data_utils import create_examples

# Set tokenizers parallelism to avoid warnings
os.environ["TOKENIZERS_PARALLELISM"] = "false"

import mlflow
import torch
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

        model, tokenizer = perform_fine_tuning(trainset, testset)
        
        # Save the fine-tuned PEFT model to mlflow with both approaches
        # First approach: Save artifacts from output directory
        mlflow.log_artifacts(v7_settings.output_dir, artifact_path="model")
        
        # Second approach: Test model loading and create comprehensive artifacts
        import tempfile
        
        with tempfile.TemporaryDirectory() as temp_model_dir:
            # Save the PEFT model locally first
            model.save_pretrained(temp_model_dir)
            tokenizer.save_pretrained(temp_model_dir)
            
            # Log the entire directory as artifacts
            mlflow.log_artifacts(temp_model_dir, artifact_path="model_peft")

            # Test the model loading within the same MLflow run context
            logger.info("Testing model loading from artifacts...")
            try:
                # Test loading the PEFT model from the saved artifacts
                from transformers import AutoTokenizer
                base_model_name = v7_settings.get_model_name()
                test_tokenizer = AutoTokenizer.from_pretrained(base_model_name)
                if test_tokenizer.pad_token is None:
                    test_tokenizer.pad_token = test_tokenizer.eos_token
                    
                from agents.triage.classifier_v7.gemma3_wrapper import (
                    Gemma3TextForSequenceClassification,
                )
                base_model = Gemma3TextForSequenceClassification.from_pretrained(
                    base_model_name,
                    num_labels=len(AGENT_TO_LABEL),
                    torch_dtype=torch.bfloat16 if torch.cuda.is_available() else torch.float32,
                    attn_implementation="eager"
                )
                
                from peft import PeftModel
                test_model = PeftModel.from_pretrained(base_model, temp_model_dir)
                
                # Create classifier and test
                test_classifier = FinetunedClassifier(model=test_model, tokenizer=test_tokenizer)
                test_result = test_classifier.classify("User: I want to know my policy due date.")
                logger.info(f"✅ Model test successful: {test_result.target_agent}")
                
            except Exception as e:
                logger.warning(f"Model test failed: {e}")

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

