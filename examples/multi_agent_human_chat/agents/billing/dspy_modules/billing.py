"""Billing Agent optimized DSPy module for production use."""
import json
import os
from pathlib import Path

import dspy
from libraries.dspy_set_language_model import dspy_set_language_model
from libraries.logger import get_console_logger
from libraries.tracing import traced_dspy_function, TracedReAct, create_tracer
from agents.billing.config import settings
from agents.billing.dspy_modules.billing_data import get_billing_info, update_billing_info

logger = get_console_logger("billing_agent.dspy")


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
      - Provide a concise, courteous message summarizing relevant billing info using specific patterns:
        - For current balance inquiries: "Your current amount due is $X.XX with a due date of YYYY-MM-DD. Your status is 'Status'."
        - For next payment info: "Your next payment of $X.XX is due on YYYY-MM-DD, and your current status is 'Status'."
        - For billing cycle inquiries: "Your current billing cycle is 'Cycle' with the next payment of $X.XX due on YYYY-MM-DD."

    GUIDELINES:
      - Maintain a polite, professional tone.
      - Only use the tools if necessary (e.g., if the user provides a policy number and requests an update or info).
      - If a policy number is missing or unclear, politely ask for it.
      - Avoid speculation or divulging irrelevant details.
      - IMPORTANT: When a user asks "How much do I owe", always use the "current amount due" format.
      - IMPORTANT: When a user asks about billing date, use the "next payment" format.
      - IMPORTANT: When a user mentions "billing cycle", use the "billing cycle" format.
      - IMPORTANT: Dates MUST be in the format YYYY-MM-DD. For example, use "2025-03-15" instead of "March 15th, 2025".

    Input Fields:
      - chat_history: A string containing the full conversation thus far.

    Output Fields:
      - final_response: The final text answer to the user regarding their billing inquiry.
    """

    chat_history: str = dspy.InputField(desc="Full conversation context.")
    final_response: str = dspy.OutputField(desc="Billing response to the user.")


def load_optimized_signature():
    """Load the optimized signature directly from our JSON file."""
    json_path = Path(__file__).resolve().parent / "optimized_billing.json"
    
    if not os.path.exists(json_path):
        logger.warning(f"No optimized signature file found at {json_path}")
        return None
    
    try:
        # Load the JSON content
        with open(str(json_path), 'r') as f:
            signature_data = json.load(f)
        
        # Create a custom signature class with the loaded instructions
        if "instructions" in signature_data:
            from dataclasses import dataclass
            
            @dataclass
            class OptimizedBillingSignature(BillingSignature):
                """Optimized signature for the billing agent."""
                pass
            
            # Set the instructions - ensure date formatting instructions are included
            instructions = signature_data["instructions"]
            if "IMPORTANT: Dates MUST be in the format YYYY-MM-DD" not in instructions:
                instructions += "\n    IMPORTANT: Dates MUST be in the format YYYY-MM-DD. For example, use \"2025-03-15\" instead of \"March 15th, 2025\"."
            
            OptimizedBillingSignature.__doc__ = instructions
            
            logger.info("Successfully loaded optimized billing signature")
            return OptimizedBillingSignature
        else:
            logger.warning("The signature file does not contain instructions")
            return None
    except Exception as e:
        logger.error(f"Error loading optimized signature: {e}")
        return None


# Load the optimized signature or use base version
try:
    # Try to load the optimized signature
    optimized_signature = load_optimized_signature()
    
    if optimized_signature:
        # Create tracer for billing agent
        tracer = create_tracer("billing_agent_optimized")
        
        # Create a TracedReAct with the optimized signature
        billing_optimized = TracedReAct(
            optimized_signature,
            tools=[get_billing_info, update_billing_info],
            name="billing_react_optimized",
            tracer=tracer,
            max_iters=5,
        )
    else:
        # Fallback to base signature
        logger.warning("Using base signature as fallback")
        tracer = create_tracer("billing_agent_fallback")
        
        # Create a TracedReAct with the base signature
        billing_optimized = TracedReAct(
            BillingSignature,
            tools=[get_billing_info, update_billing_info],
            name="billing_react_fallback",
            tracer=tracer,
            max_iters=5,
        )
except Exception as e:
    logger.error(f"Error setting up billing optimizer: {e}")
    
    # Emergency fallback with basic signature
    try:
        tracer = create_tracer("billing_agent_emergency")
        
        billing_optimized = TracedReAct(
            BillingSignature,
            tools=[get_billing_info, update_billing_info],
            name="billing_react_emergency",
            tracer=tracer,
            max_iters=5,
        )
    except Exception as fallback_error:
        logger.critical(f"Even emergency fallback failed: {fallback_error}")
        billing_optimized = dspy.Predict(BillingSignature)


@traced_dspy_function(name="billing_dspy")
def billing_optimized_dspy(chat_history: str) -> str:
    """
    Process a billing inquiry using the optimized DSPy program.
    
    Args:
        chat_history: The conversation history.
        
    Returns:
        str: The billing agent's response.
    """
    try:
        # Configure the language model
        lm = dspy_set_language_model(settings)
        
        # Get module type for debugging
        module_type = type(billing_optimized).__name__
        module_name = getattr(billing_optimized, 'name', 'unknown')
        logger.info(f"Using billing module of type {module_type} (name: {module_name})")
        
        # Call the appropriate module
        prediction = billing_optimized(chat_history=chat_history)
        
        # Handle different result types
        if hasattr(prediction, 'final_response'):
            return prediction.final_response
        elif isinstance(prediction, dict) and 'final_response' in prediction:
            return prediction['final_response']
        elif isinstance(prediction, str):
            return prediction
        else:
            logger.warning(f"Unexpected prediction type: {type(prediction)}, using string representation")
            return str(prediction)
            
    except Exception as e:
        logger.error(f"Error in billing_optimized_dspy: {e}")
        return "I apologize, but I'm having trouble processing your request right now. Could you please provide more details about your billing inquiry?"


if __name__ == "__main__":
    # Test the billing DSPy module
    test_conversation = (
        "User: Hi, I'd like to check my billing status.\n"
        "BillingAgent: Sure! Could you please provide your policy number?\n"
        "User: It's A12345.\n"
    )
    
    result = billing_optimized_dspy(test_conversation)
    print(f"Response: {result}")