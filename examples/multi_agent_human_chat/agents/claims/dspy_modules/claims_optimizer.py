"""
Optimizer for Claims Agent prompts using COPRO.

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
from typing import List
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
from agents.claims.config import settings
from agents.claims.dspy_modules.claims_dataset import create_claims_dataset, as_dspy_examples
from libraries.logger import get_console_logger

logger = get_console_logger("claims_optimizer")


class ClaimsSignature(dspy.Signature):
    """
    You are the Claims Agent for an insurance company.

    ROLE:
    - Help customers with all claims-related questions and actions, including:
      • Filing a new claim
      • Checking the status of an existing claim
      • Explaining required documentation
      • Estimating payouts and timelines
      • Updating claim details (e.g. contact info, incident description)

    TOOLS:
    - get_claim_status(claim_number: str) -> str:
        Retrieves the current status, payment estimate, next steps, and any outstanding items for a given claim. Returns JSON string.
    - file_claim(policy_number: str, claim_details: str) -> str:
        Creates a new claim under the customer's policy with the provided incident details. Returns JSON string of new claim.
    - update_claim_info(claim_number: str, field: str, new_value: str) -> str:
        Modifies a specified field (e.g., "address", "phone", "damage_description") on an existing claim. Returns JSON string of updated claim.

    RESPONSE FORMAT:
    - Respond in a clear, courteous, and professional tone.
    - Summarize the key information or confirm the action taken.
    - Example for status inquiry:
        "Your claim #123456 is currently 'In Review'. We estimate a payout of $2,300 by 2025-05-15. We're still awaiting your repair estimates—please submit them at your earliest convenience."
    - Example for filing a claim:
        "I've filed a new claim #789012 under policy ABC-123. Please upload photos of the damage and any police report within 5 business days to expedite processing."

    GUIDELINES:
    - Only invoke a tool when the user provides or requests information that requires it (a claim number for status, policy number and details to file, etc.).
    - If the user hasn't specified a claim or policy number when needed, politely request it:
        "Could you please provide your claim number so I can check its status?"
    - Do not disclose internal processes or irrelevant details.
    - Keep answers concise—focus only on what the customer needs to know or do next.
    - Always confirm changes you make:
        "I've updated your mailing address on claim #123456 as requested."

    Input Fields:
    - chat_history: str — Full conversation context.

    Output Fields:
    - final_response: str — Claims response to the user.
    """

    chat_history: str = dspy.InputField(desc="Full conversation context.")
    final_response: str = dspy.OutputField(desc="Claims response to the user.")


# Create the unoptimized react program
from libraries.tracing import TracedReAct

# Mock tools for optimization (these won't actually be called during optimization)
def mock_get_claim_status(claim_number: str):
    """Mock implementation of get_claim_status for optimization."""
    return '{"claim_number": "1001", "policy_number": "A12345", "status": "In Review", "estimate": 2300.0, "estimate_date": "2025-05-15", "next_steps": "Submit repair estimates"}'

def mock_file_claim(policy_number: str, claim_details: str):
    """Mock implementation of file_claim for optimization."""
    return '{"claim_number": "1004", "policy_number": "A12345", "status": "Filed", "next_steps": "Provide documentation"}'

def mock_update_claim_info(claim_number: str, field: str, new_value: str):
    """Mock implementation of update_claim_info for optimization."""
    return '{"claim_number": "1001", "policy_number": "A12345", "status": "Updated", "field": "' + field + '", "new_value": "' + new_value + '"}'

# Create TracedReAct program for optimization
claims_program = TracedReAct(
    ClaimsSignature,
    tools=[mock_get_claim_status, mock_file_claim, mock_update_claim_info],
    name="claims_react_optimizer",
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
    
    # Check for claim number
    if "claim #" in expected:
        try:
            claim_num_expected = expected.split("claim #")[1].split(" ")[0].strip().replace(".", "")
            if "claim #" not in predicted or claim_num_expected not in predicted:
                return 0.5  # Partial match if claim number is missing
        except IndexError:
            pass  # Handle case where the format is different
    
    # Check for status
    if "currently" in expected and "'" in expected.split("currently")[1]:
        try:
            status_expected = expected.split("currently '")[1].split("'")[0].strip()
            if "currently" not in predicted or status_expected not in predicted:
                return 0.5  # Partial match if status is missing
        except IndexError:
            pass  # Handle case where the format is different
    
    # Check for estimate amount
    if "payout of $" in expected:
        try:
            amount_expected = expected.split("payout of $")[1].split(" ")[0].strip()
            if "payout of $" not in predicted or amount_expected not in predicted:
                return 0.5  # Partial match if estimate is missing
        except IndexError:
            pass  # Handle case where the format is different
    
    # Check for policy number in filing claims
    if "policy" in expected:
        try:
            policy_expected = expected.split("policy")[1].split(".")[0].strip()
            if "policy" not in predicted or policy_expected not in predicted:
                return 0.5  # Partial match if policy number is missing
        except IndexError:
            pass  # Handle case where the format is different
    
    # If we get here, it's a good match
    return 1.0


if __name__ == "__main__":
    # Set up env & LM - explicitly disable cache for optimization
    lm = dspy_set_language_model(settings, overwrite_cache_enabled=False)
    
    # Set up MLflow
    mlflow.set_experiment("claims_agent_optimization")
    run_name = f"claims_optimization_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    with mlflow.start_run(run_name=run_name):
        # Log configuration
        mlflow.log_params({
            "model_name": "claims_agent",
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
        logger.info("Creating claims dataset...")
        raw_examples = create_claims_dataset()
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
        base_score = evaluator(claims_program)
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
            # Define CustomCOPRO class to handle incomplete model outputs
            class CustomCOPRO(COPRO):
                def propose_configuration(self, prompt_template, field_configs=None):
                    """Override to handle incomplete outputs from model"""
                    try:
                        # Try the standard way first
                        result = super().propose_configuration(prompt_template, field_configs)
                        logger.info("Standard COPRO proposal succeeded")
                        return result
                    except Exception as e:
                        logger.warning(f"Standard COPRO proposal failed: {e}")
                        
                        # Common error: missing 'proposed_instruction'
                        if "proposed_prefix_for_output_field" in str(e) or "proposed_instruction" in str(e):
                            logger.info("Creating minimal valid configuration")
                            return {
                                "proposed_instruction": prompt_template.get("instruction", 
                                    "You are the Claims Agent for an insurance company. Help customers with claims inquiries."),
                                "proposed_prefix_for_output_field": "I'll help with your claims inquiry."
                            }
                        # Any other error - re-raise
                        else:
                            raise e
            
            # Use our custom COPRO with same parameters
            logger.info("Using CustomCOPRO for optimization")
            optimizer = CustomCOPRO(
                metric=precision_metric,
                breadth=breadth,
                depth=depth
            )
            
            # Compile using our custom optimizer
            optimized_program = optimizer.compile(
                claims_program,
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
            json_path = Path(__file__).resolve().parent / "optimized_claims.json"
            
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
                        raise ValueError("Optimized program has no signature attribute")
                except Exception as simplified_save_error:
                    logger.error(f"Simplified signature save also failed: {simplified_save_error}")
                    raise
            
            # Log artifacts
            mlflow.log_artifact(str(json_path))
            
        except Exception as e:
            logger.error(f"Optimization failed: {e}")
            mlflow.log_param("optimization_error", str(e))
            
            # Save original program
            json_path = Path(__file__).resolve().parent / "optimized_claims.json"
            claims_program.save(str(json_path))
            logger.info(f"Saved original program to {json_path}")
            mlflow.log_artifact(str(json_path))