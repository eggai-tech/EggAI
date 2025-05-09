"""Policies Agent optimized DSPy module for production use."""
import json
import os
from pathlib import Path
from typing import Optional, Literal

import dspy
from opentelemetry import trace
from libraries.dspy_set_language_model import dspy_set_language_model
from libraries.logger import get_console_logger
from libraries.tracing import traced_dspy_function, TracedReAct
from agents.policies.config import settings

logger = get_console_logger("policies_agent.dspy")

PolicyCategory = Literal["auto", "life", "home", "health"]


class PolicyAgentSignature(dspy.Signature):
    """
    This signature defines the input and output for processing policy inquiries
    using a simple ReACT loop.

    Role:
    - You are the Policy Agent for an insurance company. Your job is to help users
      with inquiries about insurance policies (coverage details, premiums, etc.).
    - If the necessary policy details (e.g. a policy number) are provided, use a tool
      to retrieve policy information, it will return a JSON-formatted string if the policy is found with fields like name, premium amount, due date and policy category.
    - You can also use a tool query_policy_documentation for specific questions, you can query documentation about a policy by providing a query and a policy category retrieved from database.
    - If not, ask for the missing information.
    - Maintain a polite, concise, and helpful tone.
    - If documentation is found, please include it in the final response as summarized information, specifying the document reference formatted with parenthesis and an identifier POLICY_CATEGORY#REFERENCE (see home#3.1) or (see home#4.5.6).
    """

    chat_history: str = dspy.InputField(desc="Full conversation context.")

    policy_category: Optional[PolicyCategory] = dspy.OutputField(
        desc="Policy category."
    )
    policy_number: Optional[str] = dspy.OutputField(desc="Policy number.")
    documentation_reference: Optional[str] = dspy.OutputField(
        desc="Reference on the documentation if found (e.g. Section 3.1 or Section 4.5.6)."
    )

    final_response: str = dspy.OutputField(desc="Final response message to the user.")
    final_response_with_documentation_reference: Optional[str] = dspy.OutputField(
        desc="Final response message to the user with documentation reference."
    )


# Try to load the optimized program or use base version
try:
    json_path = Path(__file__).resolve().parent / "optimized_policies.json"
    if os.path.exists(json_path):
        logger.info(f"Loading optimized TracedReAct policies program from {json_path}")
        # Create TracedReAct with real tools
        from agents.policies.dspy_modules.policies_data import take_policy_by_number_from_database, query_policy_documentation
        
        tracer = trace.get_tracer("policies_agent_optimized")
        
        try:
            # Try standard loading method first
            policies_signature = TracedReAct.load_signature(str(json_path))
            logger.info("Successfully loaded TracedReAct signature")
            
            policies_optimized = TracedReAct(
                policies_signature,
                tools=[take_policy_by_number_from_database, query_policy_documentation],
                name="policies_react_optimized",
                tracer=tracer,
                max_iters=5,
            )
        except Exception as load_error:
            logger.warning(f"Standard signature loading failed: {load_error}")
            
            # Try loading from simplified JSON format
            try:
                import json
                with open(str(json_path), 'r') as f:
                    signature_data = json.load(f)
                
                # Create a new signature using the saved data
                from dataclasses import dataclass
                
                @dataclass
                class PoliciesCustomSignature(PolicyAgentSignature):
                    pass
                
                # Set custom instructions if available
                if "instructions" in signature_data:
                    instructions = signature_data["instructions"]
                    # Ensure date formatting instructions are included
                    if "IMPORTANT: Dates MUST be in the format YYYY-MM-DD" not in instructions:
                        instructions += "\n    IMPORTANT: Dates MUST be in the format YYYY-MM-DD. For example, use \"2025-03-15\" instead of \"March 15th, 2025\"."
                    PoliciesCustomSignature.__doc__ = instructions
                
                # Create a new TracedReAct with the custom signature
                policies_optimized = TracedReAct(
                    PoliciesCustomSignature,
                    tools=[take_policy_by_number_from_database, query_policy_documentation],
                    name="policies_react_optimized",
                    tracer=tracer,
                    max_iters=5,
                )
                
                logger.info("Successfully loaded from simplified JSON format")
            except Exception as json_load_error:
                logger.warning(f"Simplified JSON loading also failed: {json_load_error}, trying dspy.Predict")
                # Fallback to dspy.Predict if that fails
                try:
                    policies_optimized = dspy.Predict.load(str(json_path))
                    logger.info("Successfully loaded as dspy.Predict")
                except Exception as predict_load_error:
                    logger.error(f"All loading methods failed: {predict_load_error}")
                    raise
    else:
        logger.warning(f"Optimized policies program not found at {json_path}, using base version")
        policies_optimized = dspy.Predict(PolicyAgentSignature)
except Exception as e:
    logger.warning(f"Error loading optimized policies program: {e}")
    policies_optimized = dspy.Predict(PolicyAgentSignature)


@traced_dspy_function(name="policies_dspy")
def policies_optimized_dspy(chat_history: str) -> dict:
    """
    Process a policies inquiry using the optimized DSPy program.
    
    Args:
        chat_history: The conversation history.
        
    Returns:
        dict: The policies agent's response and metadata.
    """
    lm = dspy_set_language_model(settings)
    
    try:
        # Check if we're using a TracedReAct or dspy.Predict instance
        if isinstance(policies_optimized, TracedReAct):
            # For TracedReAct, we need to handle the different output format
            logger.info("Using TracedReAct optimized policies module")
            prediction = policies_optimized(chat_history=chat_history)
            
            result = {
                "final_response": prediction.final_response
            }
            
            # Add optional fields if they exist
            if hasattr(prediction, "policy_category") and prediction.policy_category:
                result["policy_category"] = prediction.policy_category
                
            if hasattr(prediction, "policy_number") and prediction.policy_number:
                result["policy_number"] = prediction.policy_number
                
            if hasattr(prediction, "documentation_reference") and prediction.documentation_reference:
                result["documentation_reference"] = prediction.documentation_reference
                
            if (hasattr(prediction, "final_response_with_documentation_reference") and 
                prediction.final_response_with_documentation_reference):
                result["final_response_with_documentation_reference"] = prediction.final_response_with_documentation_reference
                
            return result
        else:
            # For dspy.Predict, we can call directly
            logger.info("Using dspy.Predict policies module")
            prediction = policies_optimized(chat_history=chat_history)
            
            result = {
                "final_response": prediction.final_response
            }
            
            # Add optional fields if they exist
            if hasattr(prediction, "policy_category") and prediction.policy_category:
                result["policy_category"] = prediction.policy_category
                
            if hasattr(prediction, "policy_number") and prediction.policy_number:
                result["policy_number"] = prediction.policy_number
                
            if hasattr(prediction, "documentation_reference") and prediction.documentation_reference:
                result["documentation_reference"] = prediction.documentation_reference
                
            if (hasattr(prediction, "final_response_with_documentation_reference") and 
                prediction.final_response_with_documentation_reference):
                result["final_response_with_documentation_reference"] = prediction.final_response_with_documentation_reference
                
            return result
    except Exception as e:
        logger.error(f"Error in policies_optimized_dspy: {e}")
        return {
            "final_response": "I apologize, but I'm having trouble processing your request right now. Could you please provide more details about your policy inquiry?"
        }


if __name__ == "__main__":
    # Test the policies DSPy module
    test_conversation = (
        "User: I need information about my policy.\n"
        "PoliciesAgent: Sure, I can help with that. Could you please provide me with your policy number?\n"
        "User: My policy number is A12345\n"
    )
    
    result = policies_optimized_dspy(test_conversation)
    print(f"Response: {result['final_response']}")
    
    if "policy_category" in result:
        print(f"Policy category: {result['policy_category']}")
    
    if "policy_number" in result:
        print(f"Policy number: {result['policy_number']}")
    
    if "documentation_reference" in result:
        print(f"Documentation reference: {result['documentation_reference']}")
    
    if "final_response_with_documentation_reference" in result:
        print(f"Response with reference: {result['final_response_with_documentation_reference']}")