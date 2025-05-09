from pathlib import Path
from sklearn.model_selection import train_test_split

import mlflow
from dspy.evaluate import Evaluate
from dspy.teleprompt import COPRO

from agents.triage.config import Settings
from agents.triage.data_sets.loader import (
    as_dspy_examples,
    load_dataset_triage_training,
)
from agents.triage.dspy_modules.classifier_v4.classifier_v4 import classifier_v4_program
from libraries.dspy_set_language_model import dspy_set_language_model
from libraries.logger import get_console_logger

logger = get_console_logger("triage_optimizer_v4")


# ------------------------------------------------------------------
# Metric: 1 = label matches, 0 = otherwise (sufficient for DSPy's optimiser)
# ------------------------------------------------------------------
def macro_f1(example, pred, trace=None):
    return float(example.target_agent.lower() == pred.target_agent.lower())


if __name__ == "__main__":
    # ------------------------------------------------------------------
    # Load config
    # ------------------------------------------------------------------
    from dotenv import load_dotenv
    load_dotenv()
    
    settings = Settings()

    # Set up MLflow tracking
    mlflow.set_experiment("triage_classifier_optimization")
    run_name = f"classifier_v4_copro_optimization_{settings.copro_dataset_size}examples"
    
    with mlflow.start_run(run_name=run_name):
        # Calculate actual parameter values
        actual_breadth = min(5, settings.copro_breadth)
        actual_depth = min(2, settings.copro_depth)
        
        # Log configuration parameters
        mlflow.log_params({
            "model_name": "classifier_v4",
            "optimizer": "COPRO",
            "language_model": settings.language_model,
            "dataset_size": settings.copro_dataset_size,
            "copro_breadth_config": settings.copro_breadth,
            "copro_depth_config": settings.copro_depth,
            "copro_breadth_actual": actual_breadth,
            "copro_depth_actual": actual_depth,
            "speed_optimized": True
        })
        
        mlflow.dspy.autolog(
            log_compiles=True,
            log_traces=True,
            log_evals=True,
            log_traces_from_compile=True,
            log_traces_from_eval=True
        )

        # Use settings from config instead of hardcoding
        # Settings are already imported at the top, just use them directly
        lm = dspy_set_language_model(settings)
    
        # ------------------------------------------------------------------
        # Data preparation with proper train/test split
        # ------------------------------------------------------------------
        all_examples = as_dspy_examples(load_dataset_triage_training())
        
        # Use a smaller subset for faster optimization
        train_size = min(settings.copro_dataset_size, len(all_examples))
        logger.info(f"Using {train_size} examples for optimization (from total {len(all_examples)})")
        
        # Create train/test split for proper evaluation
        # Handle small datasets appropriately
        if train_size < 5:
            # For very small datasets, use the same set for train and test
            train_set = all_examples[:train_size]
            test_set = all_examples[:train_size]
            logger.info("Using same examples for train and test due to small dataset size")
        else:
            # For normal-sized datasets, use stratified split
            train_set, test_set = train_test_split(
                all_examples[:train_size],
                test_size=0.20,
                stratify=[ex.target_agent for ex in all_examples[:train_size]],
                random_state=42,
            )
    
        # ------------------------------------------------------------------
        # Create evaluator using test set
        # ------------------------------------------------------------------
        evaluator = Evaluate(devset=test_set, metric=macro_f1, num_threads=4)
        
        # First evaluate unoptimized program
        base_score = evaluator(classifier_v4_program)
        logger.info(f"Baseline zero-shot accuracy: {base_score:.3f}")
        mlflow.log_metric("baseline_accuracy", base_score)
    
        # ------------------------------------------------------------------
        # Simplified COPRO setup
        # ------------------------------------------------------------------
        logger.info(f"Using COPRO with reduced parameters - breadth={actual_breadth} (from {settings.copro_breadth}), "
                 f"depth={actual_depth} (from {settings.copro_depth})")
        
        # Create optimizer with reduced parameters for faster execution
        optimizer = COPRO(
            metric=macro_f1,
            breadth=actual_breadth,  # Use lower breadth for faster execution
            depth=actual_depth       # Use lower depth for faster execution
        )
    
        logger.info("Starting COPRO optimization...")
        try:
            # Simpler compile call with minimal parameters
            optimized_program = optimizer.compile(
                classifier_v4_program,
                trainset=train_set,
                eval_kwargs={"metric": macro_f1} 
            )
    
            # ------------------------------------------------------------------
            # Evaluate optimized program
            # ------------------------------------------------------------------
            score = evaluator(optimized_program)
            logger.info(f"Optimized program score: {score:.3f} (improvement: {score - base_score:.3f})")
            mlflow.log_metric("optimized_accuracy", score)
            mlflow.log_metric("improvement", score - base_score)
    
            # ------------------------------------------------------------------
            # Persist the optimized program
            # ------------------------------------------------------------------
            json_path = Path(__file__).resolve().parent / "optimizations_v4.json"
            optimized_program.save(str(json_path))
            logger.info(f"Saved optimized program ({score:.3f} accuracy) → {json_path}")
            mlflow.log_artifact(str(json_path))
            
        except Exception as e:
            logger.error(f"COPRO optimization failed with error: {e}")
            logger.info("Using original zero-shot program instead")
            mlflow.log_param("optimization_error", str(e))
            
            # Save the original program when optimization fails
            json_path = Path(__file__).resolve().parent / "optimizations_v4.json"
            classifier_v4_program.save(str(json_path))
            logger.info(f"Saved original program ({base_score:.3f} accuracy) → {json_path}")
            mlflow.log_artifact(str(json_path))
