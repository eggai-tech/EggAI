#!/usr/bin/env python3

import os

import dspy
import mlflow
from dotenv import load_dotenv

from agents.triage.classifier_v6.data_utils import create_training_examples
from agents.triage.classifier_v6.model_utils import (
    extract_model_id_from_dspy,
    save_model_id_to_env,
)
from agents.triage.classifier_v6.training_utils import (
    get_classification_signature,
    log_training_parameters,
    perform_fine_tuning,
    setup_mlflow_tracking,
    show_training_info,
)
from agents.triage.config import Settings

load_dotenv()
settings = Settings()

os.environ["DSPY_CACHEDIR"] = "./dspy_cache"
dspy.settings.experimental = True


def train_finetune_model(sample_size: int = 20, model_name: str = "gpt-4o-mini-2024-07-18") -> str:
    run_name = setup_mlflow_tracking(model_name)
    
    with mlflow.start_run(run_name=run_name):
        trainset = create_training_examples(sample_size)
        log_training_parameters(sample_size, model_name, len(trainset))
        
        classify = get_classification_signature()
        
        try:
            teacher_lm = dspy.LM('openai/gpt-4o-mini', max_tokens=200)
            student_lm = dspy.LM(f'openai/{model_name}', max_tokens=200)
            
            student_classify = classify.deepcopy()
            student_classify.set_lm(student_lm)
            teacher_classify = classify.deepcopy()  
            teacher_classify.set_lm(teacher_lm)
            
            classify_ft = perform_fine_tuning(
                student_classify, teacher_classify, trainset
            )
            
            test_result = classify_ft(chat_history="User: I need help with my claim")
            print(f"Test: {test_result}")
            
            finetuned_model_id = extract_model_id_from_dspy(classify_ft)
            
            if not finetuned_model_id or not finetuned_model_id.startswith('ft:'):
                error_msg = "Failed to extract fine-tuned model ID from training process. Check OpenAI dashboard for the model ID."
                print(f"Error: {error_msg}")
                raise RuntimeError(error_msg)
            
            print(f"Model: {finetuned_model_id}")
            save_model_id_to_env(finetuned_model_id)
            print("Next: source .env")
            
            mlflow.log_param("finetuned_model_id", finetuned_model_id)
            
            estimated_tokens = len(trainset) * 100
            estimated_cost = (estimated_tokens / 1_000_000) * 3.0
            mlflow.log_metric("estimated_training_cost_usd", estimated_cost)
            
            return finetuned_model_id
            
        except Exception as e:
            mlflow.log_metric("training_success", 0)
            mlflow.log_param("error_message", str(e))
            
            print(f"Failed: {e}")
            return None


if __name__ == "__main__":
    sample_size = int(os.getenv("FINETUNE_SAMPLE_SIZE", "20"))
    model_name = os.getenv("FINETUNE_BASE_MODEL", "gpt-4o-mini-2024-07-18")
    
    show_training_info()
    
    if sample_size == -1:
        print("Full dataset (cost: $10-50+)")
    else:
        cost = sample_size * 0.02
        print(f"{sample_size} samples (cost: ${cost:.1f})")
    
    if os.getenv("SKIP_CONFIRMATION") != "true":
        if input("Continue? (y/N): ").lower().strip() != 'y':
            exit(0)
    
    model_id = train_finetune_model(sample_size, model_name)
    print(f"Result: {model_id if model_id else 'Failed'}")