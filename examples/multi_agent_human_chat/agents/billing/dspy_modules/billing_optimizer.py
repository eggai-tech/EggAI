"""
Optimizer for Billing Agent prompts using COPRO.

Note on ReAct Optimization:
---------------------------
This optimizer uses COPRO to optimize a TracedReAct module, which is not
the standard use case for COPRO.

Key points:
1. We use mock tools during optimization that return fixed data
2. We save only the optimized signature, not the full program
3. We load this signature back into a TracedReAct module at runtime

This approach allows us to optimize the agent's instructions while
preserving its tool-using capabilities.
"""

import datetime
import sys
import time
from pathlib import Path

import dspy
import litellm
import mlflow
from dspy.evaluate import Evaluate
from sklearn.model_selection import train_test_split

from libraries.dspy_copro import SimpleCOPRO, save_and_log_optimized_instructions

# Configure litellm to drop unsupported parameters
litellm.drop_params = True

from agents.billing.config import settings
from .billing_dataset import (
    as_dspy_examples,
    create_billing_dataset,
)
from libraries.dspy_set_language_model import dspy_set_language_model
from libraries.logger import get_console_logger

logger = get_console_logger("billing_optimizer")


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


# Import core prompt from billing.py - single source of truth
import importlib.util
import inspect


def get_billing_signature_prompt() -> str:
    """Extract the docstring from BillingSignature without circular imports."""
    # Load the billing module dynamically
    spec = importlib.util.spec_from_file_location(
        "billing", Path(__file__).resolve().parent / "billing.py"
    )
    billing_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(billing_module)

    # Extract the docstring from BillingSignature
    return inspect.getdoc(billing_module.BillingSignature)


# Use the same prompt from the main module
class BillingSignature(dspy.Signature):
    """The billing agent signature for optimization."""

    # Get the docstring from the main BillingSignature
    __doc__ = get_billing_signature_prompt()

    chat_history: str = dspy.InputField(desc="Full conversation context.")
    final_response: str = dspy.OutputField(desc="Billing response to the user.")


# Create the unoptimized react program
from libraries.tracing import TracedReAct


# Mock tools for optimization (these won't actually be called during optimization)
def mock_get_billing_info(policy_number: str):
    """Mock implementation of get_billing_info for optimization."""
    return '{"policy_number": "A12345", "billing_cycle": "Monthly", "amount_due": 120.0, "due_date": "2026-02-01", "status": "Paid"}'


def mock_update_billing_info(policy_number: str, field: str, new_value: str):
    """Mock implementation of update_billing_info for optimization."""
    return '{"policy_number": "A12345", "billing_cycle": "Monthly", "amount_due": 120.0, "due_date": "2026-02-01", "status": "Updated"}'


# Create TracedReAct program for optimization
billing_program = TracedReAct(
    BillingSignature,
    tools=[mock_get_billing_info, mock_update_billing_info],
    name="billing_react_optimizer",
    tracer=None,  # No tracing during optimization
    max_iters=5,
)


def precision_metric(example, pred, trace=None) -> float:
    """Calculate precision score by comparing expected and predicted responses.

    This metric checks if key information from the expected response is present
    in the predicted response, regardless of exact wording.

    Args:
        example: Example containing expected response
        pred: Prediction containing final_response
        trace: Optional trace information

    Returns:
        float: Precision score from 0.0 to 1.0
    """
    expected = example.final_response.lower()
    predicted = pred.final_response.lower()

    # Extract key information from both responses
    # Check for billing amount
    if "$" in expected:
        amount_expected = expected.split("$")[1].split(" ")[0].strip()
        if "$" not in predicted or amount_expected not in predicted:
            return 0.5  # Partial match if amount is missing

    # Check for date
    if "due on" in expected:
        date_expected = expected.split("due on")[1].split(",")[0].strip()
        if "due on" not in predicted or date_expected not in predicted:
            return 0.5  # Partial match if date is missing

    # Check for status
    if "status" in expected:
        status_expected = (
            expected.split("status is")[1].strip().replace("'", "").replace(".", "")
        )
        if "status" not in predicted or status_expected not in predicted:
            return 0.5  # Partial match if status is missing

    # If we get here, it's a good match
    return 1.0


# Define the critical text that must be preserved for billing
critical_privacy_text = "NEVER reveal ANY billing information unless the user has provided a specific, valid policy number"
date_format_text = "Dates MUST be in the format YYYY-MM-DD"


def format_examples(examples, max_examples=3):
    """Format a few examples for the optimization prompt."""
    formatted = []
    for i, example in enumerate(examples[:max_examples]):
        if hasattr(example, "chat_history") and hasattr(example, "final_response"):
            formatted.append(
                f"EXAMPLE {i + 1}:\nUser input: {example.chat_history}\nExpected response: {example.final_response}\n"
            )
    return "\n".join(formatted)


if __name__ == "__main__":
    # Set up env & LM - explicitly disable cache for optimization
    lm = dspy_set_language_model(settings, overwrite_cache_enabled=False)

    # Set up MLflow
    mlflow.set_experiment("billing_agent_optimization")
    run_name = (
        f"billing_optimization_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"
    )

    with mlflow.start_run(run_name=run_name):
        # Log configuration
        mlflow.log_params(
            {
                "model_name": "billing_agent",
                "optimizer": "SimpleCOPRO",
                "language_model": settings.language_model,
            }
        )

        mlflow.dspy.autolog(
            log_compiles=True,
            log_traces=True,
            log_evals=True,
            log_traces_from_compile=True,
            log_traces_from_eval=True,
        )

        # Load dataset
        logger.info("Creating billing dataset...")
        raw_examples = create_billing_dataset()
        examples = as_dspy_examples(raw_examples)

        # Split dataset
        logger.info(f"Created {len(examples)} examples, splitting into train/test...")
        train_set, test_set = train_test_split(
            examples,
            test_size=0.1,  # Reduced test set size for faster optimization
            random_state=42,
        )
        # Use minimal subset for ultra-fast optimization
        if len(train_set) > 3:
            train_set = train_set[:3]

        # Log dataset size
        mlflow.log_params(
            {
                "total_examples": len(examples),
                "train_examples": len(train_set),
                "test_examples": len(test_set),
            }
        )

        # Create evaluator
        logger.info("Setting up evaluator...")
        evaluator = Evaluate(
            devset=test_set[:2],  # Use only 2 test examples
            metric=precision_metric,
            num_threads=1,  # Single thread for minimal overhead
        )

        # Evaluate baseline with progress indicator
        logger.info("Evaluating baseline...")
        # Start progress animation for baseline evaluation
        print_progress("Evaluating baseline")

        # Custom evaluator to show progress
        def evaluate_with_progress(program):
            # Start evaluation with active spinner

            # Define a function to show spinner during evaluation
            def show_spinner():
                elapsed = 0
                while elapsed < 60:  # Timeout after 60 seconds
                    chars = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
                    for char in chars:
                        sys.stdout.write(
                            f"\r{char} Evaluating baseline... (updating every 0.1s)"
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

        base_score = evaluate_with_progress(billing_program)
        logger.info(f"Baseline score: {base_score:.3f}")
        mlflow.log_metric("baseline_score", base_score)

        # Set up SimpleCOPRO optimizer
        logger.info("Setting up SimpleCOPRO optimizer...")
        breadth = 2  # Minimum value required by COPRO
        depth = 1  # Minimum value for ultra-fast optimization

        optimizer = SimpleCOPRO(
            metric=precision_metric,
            breadth=breadth,
            depth=depth,
            logger=logger,  # Pass our logger for consistent logging
            verbose=False,  # Disable default verbosity to use our custom progress
        )

        # Log COPRO params
        mlflow.log_params(
            {
                "copro_breadth": breadth,
                "copro_depth": depth,
            }
        )

        # Optimize program with progress indicators
        logger.info("Starting optimization...")
        try:
            # Setup progress tracking for COPRO
            print("\nStarting SimpleCOPRO optimization...")

            def compile_with_progress():
                # Start progress tracking
                print_progress("Setting up optimization")

                print_progress("Starting optimization", 0, breadth * depth)

                def show_spinner():
                    elapsed = 0
                    while elapsed < 120:  # Timeout after 120 seconds
                        chars = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
                        for char in chars:
                            sys.stdout.write(
                                f"\r{char} Optimizing... (elapsed: {int(elapsed)}s)"
                            )
                            sys.stdout.flush()
                            time.sleep(0.1)
                            elapsed += 0.1

                import threading

                spinner_thread = threading.Thread(target=show_spinner)
                spinner_thread.daemon = True
                spinner_thread.start()

                # Run compilation
                result = optimizer.compile(
                    billing_program,
                    trainset=train_set,
                    eval_kwargs={},
                    critical_text=critical_privacy_text,
                )

                print_progress(
                    "Optimization complete", breadth * depth, breadth * depth
                )
                print()  # Move to next line

                return result

            # Standard COPRO approach with progress
            logger.info("Using SimpleCOPRO optimization")
            optimized_program = compile_with_progress()

            # Evaluate optimized program with progress indicator
            logger.info("Evaluating optimized program...")
            print_progress("Evaluating optimized program")
            score = evaluate_with_progress(optimized_program)
            logger.info(
                f"Optimized score: {score:.3f} (improvement: {score - base_score:.3f})"
            )

            # Log metrics
            mlflow.log_metric("optimized_score", score)
            mlflow.log_metric("improvement", score - base_score)

            # Save optimized program using shared save function
            logger.info("Saving optimized program...")
            print_progress("Saving optimized program")
            json_path = Path(__file__).resolve().parent / "optimized_billing.json"

            # Clear progress indicator for next steps
            sys.stdout.write("\r" + " " * 60 + "\r")

            # Use the shared function to save and log instructions
            save_result = save_and_log_optimized_instructions(
                path=json_path,
                optimized_program=optimized_program,
                original_program=billing_program,
                logger=logger,
                mlflow=mlflow,
            )

            if save_result:
                logger.info("✅ Successfully saved and logged optimized instructions")
            else:
                logger.warning(
                    "⚠️ There were issues saving or logging optimized instructions"
                )

            # Clear progress indicator for next steps
            sys.stdout.write("\r" + " " * 60 + "\r")

        except Exception as e:
            # Clear any progress indicators
            sys.stdout.write("\r" + " " * 60 + "\r")
            logger.error(f"❌ Optimization failed: {e}")
            mlflow.log_param("optimization_error", str(e))

            # Save original program as fallback with progress indicator
            print_progress("Saving fallback program")
            json_path = Path(__file__).resolve().parent / "optimized_billing.json"

            # Clear progress indicator for next steps
            sys.stdout.write("\r" + " " * 60 + "\r")

            # Create a fallback emergency instruction for worst-case scenario
            emergency_instruction = "You are the Billing Agent for an insurance company. Your #1 responsibility is data privacy. NEVER reveal ANY billing information unless the user has provided a specific, valid policy number."

            # Use the shared function to save and log original instructions as fallback
            save_result = save_and_log_optimized_instructions(
                path=json_path,
                optimized_program=billing_program,  # Use original program as fallback
                original_program=None,
                logger=logger,
                mlflow=mlflow,
            )

            if save_result:
                logger.info("✅ Successfully saved and logged fallback instructions")
            else:
                logger.warning(
                    "⚠️ There were issues with fallback save - creating emergency file"
                )

                # Try one last emergency save with minimal content
                try:
                    with open(str(json_path), "w") as f:
                        f.write(
                            '{"instructions": "'
                            + emergency_instruction
                            + '", "fields": []}'
                        )
                    logger.info("✅ Created emergency minimal fallback file")
                except Exception as emergency_error:
                    logger.error(f"❌ Emergency fallback failed: {emergency_error}")
