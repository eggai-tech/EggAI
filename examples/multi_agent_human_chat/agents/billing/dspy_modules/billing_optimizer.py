"""
Optimizer for Billing Agent prompts using COPRO.

Note on ReAct Optimization:
---------------------------
This optimizer uses COPRO to optimize a TracedReAct module, which is not
the standard use case for COPRO. See OPTIMIZATION.md for full details.

Key points:
1. We use mock tools during optimization that return fixed data
2. We save only the optimized signature, not the full program
3. We load this signature back into a TracedReAct module at runtime

This approach allows us to optimize the agent's instructions while
preserving its tool-using capabilities.
"""
import os
from pathlib import Path
import datetime

import mlflow
import dspy
import litellm
from dspy.evaluate import Evaluate
from dspy.teleprompt import COPRO
from sklearn.model_selection import train_test_split

# Configure litellm to drop unsupported parameters
litellm.drop_params = True

from libraries.dspy_set_language_model import dspy_set_language_model
from agents.billing.config import settings
from agents.billing.dspy_modules.billing_dataset import create_billing_dataset, as_dspy_examples
from libraries.logger import get_console_logger

logger = get_console_logger("billing_optimizer")


class BillingSignature(dspy.Signature):
    """
    You are the Billing Agent for an insurance company.

    ROLE:
      - Assist customers with billing-related inquiries such as due amounts, billing cycles, payment statuses, etc.
      - Retrieve or update billing information as needed.
      - Provide polite, concise, and helpful answers.

    TOOLS:
      - get_billing_info(policy_number): Retrieves billing information (amount due, due date, payment status, etc.).
      - update_billing_info(policy_number, field, new_value): Updates a particular field in the billing record.

    RESPONSE FORMAT:
      - Provide a concise, courteous message summarizing relevant billing info or acknowledging an update.
        For instance:
          "Your next payment of $100 is due on 2025-02-01, and your current status is 'Paid'."

    GUIDELINES:
      - Maintain a polite, professional tone.
      - Only use the tools if necessary (e.g., if the user provides a policy number and requests an update or info).
      - If a policy number is missing or unclear, politely ask for it.
      - Avoid speculation or divulging irrelevant details.

    Input Fields:
      - chat_history: A string containing the full conversation thus far.

    Output Fields:
      - final_response: The final text answer to the user regarding their billing inquiry.
    """

    chat_history: str = dspy.InputField(desc="Full conversation context.")
    final_response: str = dspy.OutputField(desc="Billing response to the user.")


# Create the unoptimized react program
from libraries.tracing import TracedReAct

# Mock tools for optimization (these won't actually be called during optimization)
def mock_get_billing_info(policy_number: str):
    """Mock implementation of get_billing_info for optimization."""
    return '{"policy_number": "A12345", "billing_cycle": "Monthly", "amount_due": 120.0, "due_date": "2025-02-01", "status": "Paid"}'

def mock_update_billing_info(policy_number: str, field: str, new_value: str):
    """Mock implementation of update_billing_info for optimization."""
    return '{"policy_number": "A12345", "billing_cycle": "Monthly", "amount_due": 120.0, "due_date": "2025-02-01", "status": "Updated"}'

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
        status_expected = expected.split("status is")[1].strip().replace("'", "").replace(".", "")
        if "status" not in predicted or status_expected not in predicted:
            return 0.5  # Partial match if status is missing
    
    # If we get here, it's a good match
    return 1.0


if __name__ == "__main__":
    # Set up env & LM - explicitly disable cache for optimization
    lm = dspy_set_language_model(settings, overwrite_cache_enabled=False)
    
    # Set up MLflow
    mlflow.set_experiment("billing_agent_optimization")
    run_name = f"billing_optimization_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    with mlflow.start_run(run_name=run_name):
        # Log configuration
        mlflow.log_params({
            "model_name": "billing_agent",
            "optimizer": "COPRO",
            "language_model": settings.language_model,
        })
        
        mlflow.dspy.autolog(
            log_compiles=True,
            log_traces=True,
            log_evals=True,
            log_traces_from_compile=True,
            log_traces_from_eval=True
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
            random_state=42
        )
        # Use smaller subset for faster optimization
        if len(train_set) > 8:
            train_set = train_set[:8]
        
        # Log dataset size
        mlflow.log_params({
            "total_examples": len(examples),
            "train_examples": len(train_set),
            "test_examples": len(test_set),
        })
        
        # Create evaluator
        logger.info("Setting up evaluator...")
        evaluator = Evaluate(
            devset=test_set, 
            metric=precision_metric,
            num_threads=2  # Reduced for faster operation
        )
        
        # Evaluate baseline
        logger.info("Evaluating baseline...")
        base_score = evaluator(billing_program)
        logger.info(f"Baseline score: {base_score:.3f}")
        mlflow.log_metric("baseline_score", base_score)
        
        # Set up COPRO
        logger.info("Setting up COPRO optimizer...")
        breadth = 2  # Reduced for faster optimization
        depth = 1  # Reduced for faster optimization
        
        optimizer = COPRO(
            metric=precision_metric,
            breadth=breadth,
            depth=depth
        )
        
        # Log COPRO params
        mlflow.log_params({
            "copro_breadth": breadth,
            "copro_depth": depth,
        })
        
        # Optimize program
        logger.info("Starting optimization...")
        try:
            # Standard COPRO approach
            logger.info("Using standard COPRO optimization")
            optimized_program = optimizer.compile(
                billing_program,
                trainset=train_set,
                eval_kwargs={}
            )
            
            # Evaluate optimized program
            logger.info("Evaluating optimized program...")
            score = evaluator(optimized_program)
            logger.info(f"Optimized score: {score:.3f} (improvement: {score - base_score:.3f})")
            
            # Log metrics
            mlflow.log_metric("optimized_score", score)
            mlflow.log_metric("improvement", score - base_score)
            
            # Save optimized program
            logger.info("Saving optimized program...")
            json_path = Path(__file__).resolve().parent / "optimized_billing.json"
            
            try:
                # Try saving the full signature
                optimized_signature = optimized_program.signature
                optimized_signature.save(str(json_path))
                logger.info(f"Saved optimized signature to {json_path}")
            except Exception as save_error:
                logger.warning(f"Full signature save failed: {save_error}")
                
                # Fallback to manual JSON save of critical parts
                try:
                    import json
                    
                    # Extract essential signature components
                    if hasattr(optimized_program, 'signature'):
                        signature_data = {
                            "instructions": optimized_program.signature.instructions,
                            "fields": []
                        }
                        
                        # Try to extract field information
                        if hasattr(optimized_program.signature, 'fields'):
                            for field in optimized_program.signature.fields:
                                if hasattr(field, 'name') and hasattr(field, 'prefix'):
                                    signature_data["fields"].append({
                                        "name": field.name,
                                        "prefix": field.prefix
                                    })
                        
                        # Save simplified signature
                        with open(str(json_path), 'w') as f:
                            json.dump(signature_data, f, indent=2)
                        logger.info(f"Saved simplified signature to {json_path}")
                    else:
                        logger.error("Optimized program has no signature attribute")
                except Exception as simplified_save_error:
                    logger.error(f"Simplified signature save also failed: {simplified_save_error}")
            
            # Log artifacts
            mlflow.log_artifact(str(json_path))
            
        except Exception as e:
            logger.error(f"Optimization failed: {e}")
            mlflow.log_param("optimization_error", str(e))
            
            # Save original program as fallback
            json_path = Path(__file__).resolve().parent / "optimized_billing.json"
            billing_program.save(str(json_path))
            logger.info(f"Saved original program to {json_path}")
            mlflow.log_artifact(str(json_path))