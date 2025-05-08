from pathlib import Path
from types import SimpleNamespace
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

    mlflow.dspy.autolog(
        log_compiles=True,
        log_traces=True,
        log_evals=True,
        log_traces_from_compile=True,
        log_traces_from_eval=True
    )

    # Use SimpleNamespace to ensure compatibility
    lm = dspy_set_language_model(
        SimpleNamespace(
            language_model="openai/gpt-4o-mini",
            cache_enabled=True,
            language_model_api_base=None,
        )
    )

    # ------------------------------------------------------------------
    # Data preparation with proper train/test split
    # ------------------------------------------------------------------
    all_examples = as_dspy_examples(load_dataset_triage_training())
    
    # Use a smaller subset for faster optimization
    train_size = min(settings.copro_dataset_size, len(all_examples))
    print(f"Using {train_size} examples for optimization (from total {len(all_examples)})")
    
    # Create train/test split for proper evaluation
    # Handle small datasets appropriately
    if train_size < 5:
        # For very small datasets, use the same set for train and test
        train_set = all_examples[:train_size]
        test_set = all_examples[:train_size]
        print("Using same examples for train and test due to small dataset size")
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
    print(f"Baseline zero-shot accuracy: {base_score:.3f}")

    # ------------------------------------------------------------------
    # Simplified COPRO setup
    # ------------------------------------------------------------------
    print(f"Using COPRO with breadth={settings.copro_breadth}, depth={settings.copro_depth}")
    
    # Create optimizer with minimal parameters
    optimizer = COPRO(
        metric=macro_f1,
        breadth=settings.copro_breadth,
        depth=settings.copro_depth
    )

    print("Starting COPRO optimization...")
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
        print(f"Optimized program score: {score:.3f} (improvement: {score - base_score:.3f})")

        # ------------------------------------------------------------------
        # Persist the optimized program
        # ------------------------------------------------------------------
        json_path = Path(__file__).resolve().parent / "optimizations_v4.json"
        optimized_program.save(str(json_path))
        print(f"Saved optimized program ({score:.3f} accuracy) → {json_path}")
        
    except Exception as e:
        print(f"COPRO optimization failed with error: {e}")
        print("Using original zero-shot program instead")
        
        # Save the original program when optimization fails
        json_path = Path(__file__).resolve().parent / "optimizations_v4.json"
        classifier_v4_program.save(str(json_path))
        print(f"Saved original program ({base_score:.3f} accuracy) → {json_path}")
