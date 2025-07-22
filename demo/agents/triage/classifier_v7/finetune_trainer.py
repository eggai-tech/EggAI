#!/usr/bin/env python3

import os

# Set tokenizers parallelism to avoid warnings
os.environ["TOKENIZERS_PARALLELISM"] = "false"

import mlflow
from dotenv import load_dotenv

from agents.triage.classifier_v7.config import ClassifierV7Settings
from agents.triage.classifier_v7.data_utils import create_training_examples
from agents.triage.classifier_v7.model_utils import (
    save_model_id_to_env,
)
from agents.triage.classifier_v7.training_utils import (
    log_training_parameters,
    perform_fine_tuning,
    setup_mlflow_tracking,
    show_training_info,
)

load_dotenv()
v7_settings = ClassifierV7Settings()

os.environ["DSPY_CACHEDIR"] = "./dspy_cache"


def train_finetune_model(sample_size: int = 100, model_name: str = None) -> str:
    run_name = setup_mlflow_tracking(model_name)
    
    with mlflow.start_run(run_name=run_name):
        trainset = create_training_examples(sample_size)
        log_training_parameters(sample_size, model_name, len(trainset))
        
        try:
            if not model_name:
                model_name = v7_settings.get_model_name()
            
            print(f"Using model: {model_name}")
            print("Using HuggingFace Transformers for fine-tuning")
            
            student_classify = None
            teacher_classify = None
            
            classify_ft, training_output = perform_fine_tuning(
                student_classify, teacher_classify, trainset
            )
            
            test_result = classify_ft(chat_history="User: I need help with my claim")
            print(f"Test: {test_result}")
            
            import time
            timestamp = int(time.time())
            finetuned_model_id = f"{model_name.replace('/', '-')}-triage-v7-{timestamp}"
            
            print(f"Model: {finetuned_model_id}")
            save_model_id_to_env(finetuned_model_id)
            
            try:
                import mlflow.dspy as mlflow_dspy
                
                model_name_registry = "triage_classifier_v7_gemma"
                
                # Log model without signature to avoid validation issues
                mlflow_dspy.log_model(
                    classify_ft,
                    artifact_path="model",
                    registered_model_name=model_name_registry
                )
                
                print(f"Registered model: {model_name_registry}")
                mlflow.log_param("registered_model_name", model_name_registry)
                
            except Exception as e:
                print(f"Model registry failed: {e}")
                mlflow.log_param("registry_error", str(e))
            
            print("Next: source .env")
            
            mlflow.log_param("finetuned_model_id", finetuned_model_id)
            mlflow.log_metric("estimated_training_cost_usd", 0.0)
            
            return finetuned_model_id
            
        except Exception as e:
            mlflow.log_metric("training_success", 0)
            mlflow.log_param("error_message", str(e))
            
            print(f"Failed: {e}")
            return None


if __name__ == "__main__":
    sample_size = int(os.getenv("FINETUNE_SAMPLE_SIZE", "100"))
    model_name = os.getenv("FINETUNE_BASE_MODEL", None)
    
    show_training_info()
    
    if sample_size == -1:
        print("Full dataset (local training)")
    else:
        print(f"{sample_size} samples (local training)")
    
    if os.getenv("SKIP_CONFIRMATION") != "true":
        if input("Continue? (y/N): ").lower().strip() != 'y':
            exit(0)
    
    model_id = train_finetune_model(sample_size, model_name)
    print(f"Result: {model_id if model_id else 'Failed'}")