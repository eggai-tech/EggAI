"""Training utilities for fine-tuning."""

from datetime import datetime

import dspy
import mlflow


def setup_mlflow_tracking(model_name: str) -> str:
    mlflow.dspy.autolog()
    mlflow.set_experiment("triage_classifier")
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    return f"v6_{timestamp}"


def get_classification_signature():
    class TriageClassification(dspy.Signature):
        """Classify chat messages to appropriate insurance support agents."""
        chat_history = dspy.InputField(desc="The conversation history")
        target_agent = dspy.OutputField(desc="Target agent: BillingAgent, PolicyAgent, ClaimsAgent, EscalationAgent, or ChattyAgent")
    
    return dspy.Predict(TriageClassification)


def log_training_parameters(sample_size: int, model_name: str, trainset_size: int):
    mlflow.log_param("version", "v6")
    mlflow.log_param("model", model_name)
    mlflow.log_param("samples", sample_size)
    mlflow.log_param("examples", trainset_size)


def perform_fine_tuning(student_classify, teacher_classify, trainset):
    import threading
    import time
    
    optimizer = dspy.BootstrapFinetune(num_threads=1)
    
    print("Starting fine-tuning", end="", flush=True)
    
    # Progress indicator that runs during training
    progress_active = True
    def show_progress():
        while progress_active:
            print(".", end="", flush=True)
            time.sleep(3)
    
    progress_thread = threading.Thread(target=show_progress, daemon=True)
    progress_thread.start()
    
    start_time = time.time()
    
    # Don't capture output so we can see progress in real time
    try:
        classify_ft = optimizer.compile(
            student_classify,
            teacher=teacher_classify,
            trainset=trainset
        )
        captured_output = "Training completed successfully"
    except Exception as e:
        captured_output = f"Training error: {e}"
        raise
    finally:
        progress_active = False
    
    training_time = time.time() - start_time
    
    print(f"\nCompleted in {training_time:.1f}s")
    
    mlflow.log_metric("training_time_seconds", training_time)
    mlflow.log_metric("training_success", 1)
    
    return classify_ft, captured_output


def show_training_info():
    print("Model: GPT-4o-mini-2024-07-18")
    print("Cost: $3/1M training tokens, $0.30/$1.20/1M inference tokens")
