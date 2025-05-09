"""
Optimizer for Policies Agent prompts using COPRO.

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
from typing import List, Optional, Literal
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
from agents.policies.config import settings
from agents.policies.dspy_modules.policies_dataset import create_policies_dataset, as_dspy_examples
from libraries.logger import get_console_logger

logger = get_console_logger("policies_optimizer")

PolicyCategory = Literal["auto", "life", "home", "health"]


class SimplePolicyAgentSignature(dspy.Signature):
    """
    You are the Policy Agent for an insurance company.

    ROLE:
    - Help customers with policy-related inquiries such as coverage details, premium amounts, etc.
    - Retrieve policy information or documentation as needed.
    - Provide polite, concise, and helpful answers.

    TOOLS:
    - get_policy_info(policy_number): Retrieves policy information (premium amount, due date, category, etc.).
    - query_policy_documentation(category, query): Searches policy documentation for specific information.

    RESPONSE FORMAT:
    - Provide a concise, courteous message that answers the user's policy question.
    - If documentation is referenced, include it in the format: (see category#section), for example (see home#3.1).

    GUIDELINES:
    - Maintain a polite, professional tone.
    - Only use the tools if necessary (e.g., if the user provides a policy number and requests info).
    - If a policy number is missing or unclear, politely ask for it.
    - Avoid speculation or divulging irrelevant details.

    Input Fields:
    - chat_history: A string containing the full conversation thus far.

    Output Fields:
    - final_response: The final text answer to the user regarding their policy inquiry.
    """

    chat_history: str = dspy.InputField(desc="Full conversation context.")
    final_response: str = dspy.OutputField(desc="Policy response to the user.")


# Create the unoptimized react program
from libraries.tracing import TracedReAct

# Mock tools for optimization (these won't actually be called during optimization)
def mock_take_policy_by_number_from_database(policy_number: str):
    """Mock implementation of take_policy_by_number_from_database for optimization."""
    return '{"policy_number": "A12345", "name": "John Doe", "policy_category": "auto", "premium_amount": 500, "due_date": "2025-03-01"}'

def mock_query_policy_documentation(query: str, policy_category: str):
    """Mock implementation of query_policy_documentation for optimization."""
    return '[{"category": "' + policy_category + '", "section": "2.1", "content": "Coverage details for ' + query + '"}]'

# Create TracedReAct program for optimization
policies_program = TracedReAct(
    SimplePolicyAgentSignature,
    tools=[mock_take_policy_by_number_from_database, mock_query_policy_documentation],
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
    policy_numbers = [word for word in expected.split() if len(word) >= 2 and word[0].isalpha() and any(c.isdigit() for c in word)]
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
        if len(common_words_expected.intersection(common_words_predicted)) >= 0.5 * len(common_words_expected):
            return 1.0
        return 0.5
    
    # Calculate final score
    return score / total_checks


if __name__ == "__main__":
    # Set up env & LM - explicitly disable cache for optimization
    lm = dspy_set_language_model(settings, overwrite_cache_enabled=False)
    
    # Set up MLflow
    mlflow.set_experiment("policies_agent_optimization")
    run_name = f"policies_optimization_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    with mlflow.start_run(run_name=run_name):
        # Log configuration
        mlflow.log_params({
            "model_name": "policies_agent",
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
        logger.info("Creating policies dataset...")
        raw_examples = create_policies_dataset()
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
            metric=simple_precision_metric,
            num_threads=2  # Reduced for faster operation
        )
        
        # Evaluate baseline
        logger.info("Evaluating baseline...")
        base_score = evaluator(policies_program)
        logger.info(f"Baseline score: {base_score:.3f}")
        mlflow.log_metric("baseline_score", base_score)
        
        # Set up COPRO
        logger.info("Setting up COPRO optimizer...")
        breadth = 2  # Reduced for faster optimization
        depth = 1  # Reduced for faster optimization
        
        optimizer = COPRO(
            metric=simple_precision_metric,
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
                                    "You are the Policy Agent for an insurance company. Help customers with policy inquiries."),
                                "proposed_prefix_for_output_field": "I'll help with your policy inquiry."
                            }
                        # Any other error - re-raise
                        else:
                            raise e
            
            # Use our custom COPRO with same parameters
            logger.info("Using CustomCOPRO for optimization")
            optimizer = CustomCOPRO(
                metric=simple_precision_metric,
                breadth=breadth,
                depth=depth
            )
            
            # Compile using our custom optimizer
            optimized_program = optimizer.compile(
                policies_program,
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
            json_path = Path(__file__).resolve().parent / "optimized_policies.json"
            
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
            json_path = Path(__file__).resolve().parent / "optimized_policies.json"
            policies_program.save(str(json_path))
            logger.info(f"Saved original program to {json_path}")
            mlflow.log_artifact(str(json_path))