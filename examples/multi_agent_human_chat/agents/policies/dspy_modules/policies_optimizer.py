"""
Optimizer for Policies Agent prompts using COPRO.

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

from agents.policies.config import settings
from agents.policies.dspy_modules.policies_dataset import (
    as_dspy_examples,
    create_policies_dataset,
)
from libraries.dspy_set_language_model import dspy_set_language_model
from libraries.logger import get_console_logger

logger = get_console_logger("policies_optimizer")


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


from typing import Literal, Optional

PolicyCategory = Literal["auto", "life", "home", "health"]


# Rather than causing potential circular imports, we'll use a function to get the PolicyAgentSignature prompt
import importlib.util
import inspect


def get_policy_agent_signature_prompt() -> str:
    """Extract the docstring from PolicyAgentSignature without circular imports."""
    # Load the policies module dynamically
    spec = importlib.util.spec_from_file_location(
        "policies", Path(__file__).resolve().parent / "policies.py"
    )
    policies_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(policies_module)

    # Extract the docstring from PolicyAgentSignature
    return inspect.getdoc(policies_module.PolicyAgentSignature)


# Use the same prompt from the main module
class SimplePolicyAgentSignature(dspy.Signature):
    """The policy agent signature for optimization."""

    # Get the docstring from the main PolicyAgentSignature
    __doc__ = get_policy_agent_signature_prompt()

    chat_history: str = dspy.InputField(desc="Full conversation context.")

    policy_category: Optional[PolicyCategory] = dspy.OutputField(
        desc="Policy category if identified."
    )
    policy_number: Optional[str] = dspy.OutputField(
        desc="Policy number if provided by user."
    )
    documentation_reference: Optional[str] = dspy.OutputField(
        desc="Reference on the documentation if found (e.g. Section 3.1)."
    )

    final_response: str = dspy.OutputField(desc="Final response message to the user.")


# Create the unoptimized react program
from libraries.tracing import TracedReAct


# Mock tools for optimization (these won't actually be called during optimization)
def take_policy_by_number_from_database(policy_number: str):
    """Mock implementation of take_policy_by_number_from_database for optimization."""
    return '{"policy_number": "A12345", "name": "John Doe", "policy_category": "auto", "premium_amount": 500, "premium_amount_usd": "$500.00", "due_date": "2026-03-01", "payment_due_date": "2026-03-01", "next_payment_date": "2026-03-01"}'


def query_policy_documentation(query: str, policy_category: str):
    """Mock implementation of query_policy_documentation for optimization."""
    return (
        '[{"category": "'
        + policy_category
        + '", "section": "2.1", "content": "Coverage details for '
        + query
        + '"}]'
    )


# Create TracedReAct program for optimization
policies_program = TracedReAct(
    SimplePolicyAgentSignature,
    tools=[take_policy_by_number_from_database, query_policy_documentation],
    name="policies_react_optimizer",
    tracer=None,  # No tracing during optimization
    max_iters=5,
)


def simple_precision_metric(example, pred, trace=None) -> float:
    """Calculate a simplified precision score by comparing expected and predicted responses.

    This metric checks for basic accuracy of the response - checking for policy numbers,
    premium amounts, and dates if present.

    Args:
        example: Example containing expected response
        pred: Prediction containing final_response
        trace: Optional trace information

    Returns:
        float: Precision score from 0.0 to 1.0
    """
    expected = example.final_response.lower()
    predicted = pred.final_response.lower()

    score = 0.0
    total_checks = 0

    # Check for policy numbers (format: letter followed by numbers)
    policy_numbers = [
        word
        for word in expected.split()
        if len(word) >= 2 and word[0].isalpha() and any(c.isdigit() for c in word)
    ]
    for policy in policy_numbers:
        total_checks += 1
        if policy in predicted:
            score += 1.0

    # Check for premium amount
    if "$" in expected:
        total_checks += 1
        try:
            amount_expected = expected.split("$")[1].split(" ")[0].strip()
            if "$" in predicted and amount_expected in predicted:
                score += 1.0
        except (IndexError, ValueError):
            pass

    # Check for date
    if "due on" in expected:
        total_checks += 1
        try:
            date_expected = expected.split("due on")[1].split(".")[0].strip()
            if "due on" in predicted and date_expected in predicted:
                score += 1.0
        except (IndexError, ValueError):
            pass

    # Check for documentation references (e.g., "auto#2.1")
    doc_refs = [word for word in expected.split() if "#" in word]
    for ref in doc_refs:
        total_checks += 1
        if ref in predicted:
            score += 1.0

    # If no specific checks were made, compare general content similarity
    if total_checks == 0:
        common_words_expected = set(expected.split())
        common_words_predicted = set(predicted.split())
        if len(common_words_expected.intersection(common_words_predicted)) >= 0.5 * len(
            common_words_expected
        ):
            return 1.0
        return 0.5

    # Calculate final score
    return score / total_checks


if __name__ == "__main__":
    # Set up env & LM - explicitly disable cache for optimization
    lm = dspy_set_language_model(settings, overwrite_cache_enabled=False)

    # Set up MLflow
    mlflow.set_experiment("policies_agent_optimization")
    run_name = (
        f"policies_optimization_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"
    )

    with mlflow.start_run(run_name=run_name):
        # Log configuration
        mlflow.log_params(
            {
                "model_name": "policies_agent",
                "optimizer": "COPRO",
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
        logger.info("Creating policies dataset...")
        raw_examples = create_policies_dataset()
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
            metric=simple_precision_metric,
            num_threads=1,  # Single thread for minimal overhead
        )

        # Evaluate baseline with progress indicator
        logger.info("Evaluating baseline...")
        # Start progress animation for baseline evaluation
        print_progress("Evaluating baseline")

        # Custom evaluator to show progress
        def evaluate_with_progress(program):
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

            import threading

            spinner_thread = threading.Thread(target=show_spinner)
            spinner_thread.daemon = True
            spinner_thread.start()

            # Run evaluation
            result = evaluator(program)

            # Stop progress animation
            sys.stdout.write("\r" + " " * 60 + "\r")  # Clear the line
            return result

        base_score = evaluate_with_progress(policies_program)
        logger.info(f"Baseline score: {base_score:.3f}")
        mlflow.log_metric("baseline_score", base_score)

        # Set up a custom COPRO implementation for simpler LLMs
        logger.info("Setting up custom COPRO optimizer for simpler LLMs...")
        breadth = 2  # Minimum value required by COPRO
        depth = 1  # Minimum value for ultra-fast optimization

        # Use the shared SimpleCOPRO class for simpler LLMs
        # Define the critical text that must be preserved for policies
        critical_policy_text = (
            "NEVER reveal ANY policy details without EXPLICIT policy number"
        )

        # Use our custom COPRO implementation
        optimizer = SimpleCOPRO(
            metric=simple_precision_metric,
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
            print("\nStarting COPRO optimization...")

            # Using a custom approach without monkey patching
            def compile_with_progress():
                # Start progress tracking
                print_progress("Setting up optimization")
                logger.info("====== DETAILED DEBUGGING FOR COPRO OPTIMIZATION ======")

                # Examine first example
                if train_set and len(train_set) > 0:
                    example = train_set[0]
                    logger.info(f"First example type: {type(example)}")
                    logger.info(f"First example attributes: {dir(example)}")
                    logger.info(f"First example content: {str(example)[:200]}...")
                else:
                    logger.error("No training examples available!")

                # Debug signature
                logger.info(
                    f"Signature docstring sample: {policies_program.signature.__doc__[:200]}..."
                )
                logger.info(f"Signature type: {type(policies_program.signature)}")

                # Debug instruction proposal
                try:
                    # Test instruction proposal directly
                    from dspy.teleprompt.copro_optimizer import (
                        BasicGenerateInstruction,
                    )

                    logger.info("Testing BasicGenerateInstruction directly")

                    # Check BasicGenerateInstruction
                    logger.info(
                        f"BasicGenerateInstruction fields: {BasicGenerateInstruction.__init__.__annotations__ if hasattr(BasicGenerateInstruction.__init__, '__annotations__') else 'No annotations'}"
                    )

                    # Print BasicGenerateInstruction details
                    try:
                        ip_fields = [
                            (fname, str(ftype))
                            for fname, ftype in vars(BasicGenerateInstruction).items()
                            if not fname.startswith("_")
                        ]
                        logger.info(f"BasicGenerateInstruction fields: {ip_fields}")
                    except Exception as field_error:
                        logger.info(
                            f"Could not extract BasicGenerateInstruction fields: {field_error}"
                        )

                    # Try simple prediction
                    try:
                        from dspy.predict import Predict

                        test_program = Predict(BasicGenerateInstruction)
                        logger.info("Created test program for instruction proposal")

                        # Context for instruction proposal
                        context = f"Original signature docstring:\n{policies_program.signature.__doc__[:500]}"
                        logger.info(f"Context sample: {context[:200]}...")

                        # Try with a direct prediction
                        logger.info(
                            "Attempting direct prediction for instruction proposal..."
                        )

                        # Try to run lm in an isolated way
                        if hasattr(example, "with_answer"):
                            example_with_answer = example.with_answer()
                            logger.info(
                                f"Example with answer: {type(example_with_answer)}"
                            )
                        else:
                            logger.info("Example doesn't have with_answer method")
                            example_with_answer = example

                        # Log LM information
                        try:
                            # Different versions of DSPy have different module structures
                            try:
                                import dspy.utils

                                logger.info(
                                    f"DSPy utils available: {dir(dspy.utils)[:5]}..."
                                )
                            except ImportError:
                                logger.warning("Could not import dspy.utils")

                            # Try to access current language model
                            import dspy

                            logger.info(
                                f"Current LM via dspy module: {dspy.settings.lm}"
                            )
                            logger.info(f"LM type: {type(dspy.settings.lm)}")
                        except Exception as lm_error:
                            logger.error(f"Error getting LM: {lm_error}")

                    except Exception as pred_error:
                        logger.error(f"Error in test prediction: {pred_error}")
                        import traceback

                        logger.error(
                            f"Test prediction traceback: {traceback.format_exc()}"
                        )

                except Exception as ip_error:
                    logger.error(f"Error testing instruction proposal: {ip_error}")
                    import traceback

                    logger.error(
                        f"InstructionProposal test traceback: {traceback.format_exc()}"
                    )

                # Run optimization with active spinner
                print_progress("Starting optimization", 0, breadth * depth)

                # Define a function to show active spinner during optimization
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

                # Start spinner in a separate thread
                import threading

                spinner_thread = threading.Thread(target=show_spinner)
                spinner_thread.daemon = True
                spinner_thread.start()

                # Run compilation with more detailed logging
                try:
                    logger.info("Calling optimizer.compile...")
                    result = optimizer.compile(
                        policies_program,
                        trainset=train_set,
                        eval_kwargs={},
                        critical_text=critical_policy_text,
                    )
                    logger.info("optimizer.compile completed successfully")
                    return result
                except Exception as compile_error:
                    logger.error(f"Error during COPRO compilation: {compile_error}")
                    import traceback

                    logger.error(
                        f"COPRO compilation traceback: {traceback.format_exc()}"
                    )
                    raise
                finally:
                    # Manually show complete progress
                    print_progress(
                        "Optimization complete", breadth * depth, breadth * depth
                    )
                    print()  # Move to next line

            # Standard COPRO approach with progress
            logger.info("Using standard COPRO optimization")
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

            # Save optimized program
            logger.info("Saving optimized program...")
            print_progress("Saving optimized program")
            json_path = Path(__file__).resolve().parent / "optimized_policies.json"

            # Clear progress indicator for next steps
            sys.stdout.write("\r" + " " * 60 + "\r")

            # Use the shared function to save and log instructions
            save_result = save_and_log_optimized_instructions(
                path=json_path,
                optimized_program=optimized_program,
                original_program=policies_program,
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

            # Log detailed error information
            import traceback

            detailed_traceback = traceback.format_exc()
            logger.error(
                f"====== DETAILED ERROR TRACEBACK ======\n{detailed_traceback}"
            )

            # Extract and log the error chain
            logger.error("====== ERROR CHAIN ======")
            current_exception = e
            error_chain = []
            while current_exception:
                error_chain.append(
                    f"{type(current_exception).__name__}: {str(current_exception)}"
                )
                current_exception = current_exception.__cause__
            logger.error("Error chain: " + " -> ".join(error_chain))

            # Log to MLflow
            try:
                mlflow.log_param("optimization_error", str(e))
                mlflow.log_param("error_type", type(e).__name__)
                mlflow.log_text(detailed_traceback, "error_traceback.txt")
            except Exception as mlflow_error:
                logger.error(f"❌ Failed to log error to MLflow: {mlflow_error}")

            # Save original program as fallback with progress indicator
            print_progress("Saving fallback program")
            json_path = Path(__file__).resolve().parent / "optimized_policies.json"

            # Clear progress indicator for next steps
            sys.stdout.write("\r" + " " * 60 + "\r")

            # Create a fallback emergency instruction for worst-case scenario
            emergency_instruction = "You are the Policy Agent for an insurance company. Your #1 responsibility is data privacy. NEVER reveal ANY policy details without EXPLICIT policy number."

            # Use the shared function to save and log original instructions as fallback
            save_result = save_and_log_optimized_instructions(
                path=json_path,
                optimized_program=policies_program,  # Use original program as fallback
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
