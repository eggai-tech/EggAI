import sys
import time
from pathlib import Path

import mlflow
from dspy.evaluate import Evaluate
from dspy.teleprompt import COPRO
from sklearn.model_selection import train_test_split

from agents.triage.config import Settings
from agents.triage.data_sets.loader import (
    as_dspy_examples,
    load_dataset_triage_training,
)
from agents.triage.dspy_modules.classifier_v4.classifier_v4 import classifier_v4_program
from libraries.ml.dspy.language_model import dspy_set_language_model
from libraries.observability.logger import get_console_logger

logger = get_console_logger("triage_optimizer_v4")


# Progress indicator function
def print_progress(message, progress=None, total=None):
    """
    Print a progress message to the console with optional progress bar.

    Args:
        message: Text message to display
        progress: Current progress value (optional)
        total: Total progress value (optional)
    """
    if progress is not None and total is not None:
        # Calculate percentage
        percent = min(100, int(progress / total * 100))
        bar_length = 30
        filled_length = int(bar_length * progress // total)

        # Create the progress bar
        bar = "█" * filled_length + "░" * (bar_length - filled_length)

        # Print the progress bar and message
        sys.stdout.write(f"\r{message}: [{bar}] {percent}% ({progress}/{total})")
        sys.stdout.flush()
    else:
        # Just print the message with a spinner
        chars = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        spinner = chars[int(time.time() * 10) % len(chars)]
        sys.stdout.write(f"\r{spinner} {message}...")
        sys.stdout.flush()


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
        # Calculate actual parameter values - ensuring breadth is at least 2
        actual_breadth = max(2, min(5, settings.copro_breadth))
        actual_depth = min(2, settings.copro_depth)

        # Log configuration parameters
        mlflow.log_params(
            {
                "model_name": "classifier_v4",
                "optimizer": "COPRO",
                "language_model": settings.language_model,
                "dataset_size": settings.copro_dataset_size,
                "copro_breadth_config": settings.copro_breadth,
                "copro_depth_config": settings.copro_depth,
                "copro_breadth_actual": actual_breadth,
                "copro_depth_actual": actual_depth,
                "speed_optimized": True,
            }
        )

        mlflow.dspy.autolog(
            log_compiles=True,
            log_traces=True,
            log_evals=True,
            log_traces_from_compile=True,
            log_traces_from_eval=True,
        )

        # Use settings from config instead of hardcoding
        # Settings are already imported at the top, just use them directly
        lm = dspy_set_language_model(settings)

        # ------------------------------------------------------------------
        # Data preparation with proper train/test split
        # ------------------------------------------------------------------
        logger.info("Loading and preparing dataset...")
        print_progress("Loading dataset")

        all_examples = as_dspy_examples(load_dataset_triage_training())

        # Use a smaller subset for faster optimization
        train_size = min(settings.copro_dataset_size, len(all_examples))
        sys.stdout.write("\r" + " " * 60 + "\r")  # Clear the spinner
        logger.info(
            f"✅ Using {train_size} examples for optimization (from total {len(all_examples)})"
        )

        # Create train/test split for proper evaluation
        print_progress("Creating train/test split")

        # Handle small datasets appropriately
        if train_size < 5:
            # For very small datasets, use the same set for train and test
            train_set = all_examples[:train_size]
            test_set = all_examples[:train_size]
            sys.stdout.write("\r" + " " * 60 + "\r")  # Clear the spinner
            logger.info(
                "✅ Using same examples for train and test due to small dataset size"
            )
        else:
            # For normal-sized datasets, use stratified split
            train_set, test_set = train_test_split(
                all_examples[:train_size],
                test_size=0.20,
                stratify=[ex.target_agent for ex in all_examples[:train_size]],
                random_state=42,
            )
            sys.stdout.write("\r" + " " * 60 + "\r")  # Clear the spinner
            logger.info(
                f"✅ Created stratified split: {len(train_set)} train, {len(test_set)} test examples"
            )

        # ------------------------------------------------------------------
        # Create evaluator using test set
        # ------------------------------------------------------------------
        logger.info("Setting up evaluation...")
        print_progress("Creating evaluator")
        evaluator = Evaluate(devset=test_set, metric=macro_f1, num_threads=4)
        sys.stdout.write("\r" + " " * 60 + "\r")  # Clear the spinner

        # Custom evaluator to show progress
        def evaluate_with_progress(program, message="Evaluating"):
            def show_spinner():
                elapsed = 0
                while elapsed < 60:  # Timeout after 60 seconds
                    chars = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
                    for char in chars:
                        sys.stdout.write(
                            f"\r{char} {message}... (elapsed: {int(elapsed)}s)"
                        )
                        sys.stdout.flush()
                        time.sleep(0.1)
                        elapsed += 0.1

            # Start spinner in a separate thread
            import threading

            spinner_thread = threading.Thread(target=show_spinner)
            spinner_thread.daemon = True
            spinner_thread.start()

            # Run evaluation
            result = evaluator(program)

            # Stop progress animation
            sys.stdout.write("\r" + " " * 60 + "\r")  # Clear the line
            return result

        # First evaluate unoptimized program
        base_score = evaluate_with_progress(
            classifier_v4_program, "Evaluating baseline zero-shot model"
        )
        logger.info(f"✅ Baseline zero-shot accuracy: {base_score:.3f}")
        mlflow.log_metric("baseline_accuracy", base_score)

        # ------------------------------------------------------------------
        # Simplified COPRO setup
        # ------------------------------------------------------------------
        logger.info(
            f"Using COPRO with reduced parameters - breadth={actual_breadth} (from {settings.copro_breadth}), "
            f"depth={actual_depth} (from {settings.copro_depth})"
        )

        # Create optimizer with reduced parameters for faster execution
        optimizer = COPRO(
            metric=macro_f1,
            breadth=actual_breadth,  # Use lower breadth for faster execution
            depth=actual_depth,  # Use lower depth for faster execution
            verbose=False,  # Disable default verbosity to use our custom progress
        )

        logger.info("Starting COPRO optimization...")
        print("\nStarting COPRO optimization...\n")

        try:
            # Using a custom approach without monkey patching
            def compile_with_progress():
                # Start progress tracking
                print_progress("Setting up optimization")

                # Define a function to show active spinner during optimization
                def show_spinner():
                    elapsed = 0
                    while elapsed < 300:  # Timeout after 5 minutes (300 seconds)
                        chars = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
                        for char in chars:
                            sys.stdout.write(
                                f"\r{char} Optimizing COPRO... (elapsed: {int(elapsed)}s)"
                            )
                            sys.stdout.flush()
                            time.sleep(0.1)
                            elapsed += 0.1

                # Start spinner in a separate thread
                import threading

                spinner_thread = threading.Thread(target=show_spinner)
                spinner_thread.daemon = True
                spinner_thread.start()

                # Run compilation directly - don't include metric in eval_kwargs since it's already provided to COPRO
                result = optimizer.compile(
                    classifier_v4_program,
                    trainset=train_set,
                    eval_kwargs={},  # Empty dict to avoid duplicate metric parameter
                )

                # Show optimization completion
                sys.stdout.write("\r" + " " * 60 + "\r")
                print("✓ Optimization complete!")

                return result

            # Execute optimization
            optimized_program = compile_with_progress()

            # ------------------------------------------------------------------
            # Evaluate optimized program
            # ------------------------------------------------------------------
            score = evaluate_with_progress(
                optimized_program, "Evaluating optimized model"
            )
            logger.info(
                f"✅ Optimized program score: {score:.3f} (improvement: {score - base_score:.3f})"
            )
            mlflow.log_metric("optimized_accuracy", score)
            mlflow.log_metric("improvement", score - base_score)

            # ------------------------------------------------------------------
            # Persist the optimized program
            # ------------------------------------------------------------------
            print_progress("Saving optimized program")
            json_path = Path(__file__).resolve().parent / "optimizations_v4.json"

            try:
                optimized_program.save(str(json_path))
                sys.stdout.write("\r" + " " * 60 + "\r")  # Clear the spinner
                logger.info(
                    f"✅ Saved optimized program ({score:.3f} accuracy) → {json_path}"
                )
            except Exception as save_error:
                sys.stdout.write("\r" + " " * 60 + "\r")  # Clear the spinner
                logger.error(f"❌ Error saving optimized program: {save_error}")
                logger.info("Trying alternative save method...")

                try:
                    # Try a different way to save the program
                    import json

                    with open(str(json_path), "w") as f:
                        json.dump(optimized_program.dumps(), f, indent=2)
                    logger.info("✅ Saved optimized program using alternative method")
                except Exception as alt_save_error:
                    logger.error(
                        f"❌ Alternative save method also failed: {alt_save_error}"
                    )

            # Log artifacts with progress
            print_progress("Logging artifacts to MLflow")
            mlflow.log_artifact(str(json_path))
            sys.stdout.write("\r" + " " * 60 + "\r")  # Clear the spinner
            logger.info("✅ Artifacts logged successfully")

        except Exception as e:
            sys.stdout.write("\r" + " " * 60 + "\r")  # Clear any progress indicators
            logger.error(f"❌ COPRO optimization failed with error: {e}")
            logger.info("Using original zero-shot program instead")
            mlflow.log_param("optimization_error", str(e))

            # Save the original program when optimization fails with progress tracking
            print_progress("Saving fallback program")
            json_path = Path(__file__).resolve().parent / "optimizations_v4.json"

            try:
                classifier_v4_program.save(str(json_path))
                sys.stdout.write("\r" + " " * 60 + "\r")  # Clear the spinner
                logger.info(
                    f"✅ Saved original program ({base_score:.3f} accuracy) → {json_path}"
                )
            except Exception as save_error:
                sys.stdout.write("\r" + " " * 60 + "\r")  # Clear the spinner
                logger.error(f"❌ Error saving original program: {save_error}")
                logger.info("Trying alternative save method...")

                try:
                    # Try a different way to save the program
                    import json

                    with open(str(json_path), "w") as f:
                        json.dump(classifier_v4_program.dumps(), f, indent=2)
                    logger.info("✅ Saved original program using alternative method")
                except Exception as alt_save_error:
                    logger.error(
                        f"❌ Alternative save method also failed: {alt_save_error}"
                    )

            # Log artifacts with progress
            print_progress("Logging artifacts to MLflow")
            mlflow.log_artifact(str(json_path))
            sys.stdout.write("\r" + " " * 60 + "\r")  # Clear the spinner
            logger.info("✅ Fallback artifacts logged successfully")
