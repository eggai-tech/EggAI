"""Billing Agent optimized DSPy module for production use."""
import json
import os
from pathlib import Path

import dspy
from libraries.dspy_set_language_model import dspy_set_language_model
from libraries.logger import get_console_logger
from libraries.tracing import traced_dspy_function
from agents.billing.config import settings

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


# Try to load the optimized program or use base version
try:
    json_path = Path(__file__).resolve().parent / "optimized_billing.json"
    if os.path.exists(json_path):
        logger.info(f"Loading optimized TracedReAct billing program from {json_path}")
        # Create TracedReAct with real tools
        from agents.billing.agent import get_billing_info, update_billing_info
        from libraries.tracing import create_tracer
        
        tracer = create_tracer("billing_agent_optimized")
        
        try:
            # Try standard loading method first
            billing_signature = TracedReAct.load_signature(str(json_path))
            billing_optimized = TracedReAct(
                billing_signature,
                tools=[get_billing_info, update_billing_info],
                name="billing_react_optimized",
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
                class BillingCustomSignature(BillingSignature):
                    pass
                
                # Set custom instructions if available
                if "instructions" in signature_data:
                    BillingCustomSignature.__doc__ = signature_data["instructions"]
                
                # Create a new TracedReAct with the custom signature
                billing_optimized = TracedReAct(
                    BillingCustomSignature,
                    tools=[get_billing_info, update_billing_info],
                    name="billing_react_optimized",
                    tracer=tracer,
                    max_iters=5,
                )
                
                logger.info("Successfully loaded from simplified JSON format")
            except Exception as json_load_error:
                logger.error(f"Simplified JSON loading also failed: {json_load_error}")
                raise
    else:
        logger.warning(f"Optimized billing program not found at {json_path}, using base version")
        billing_optimized = dspy.Predict(BillingSignature)
except Exception as e:
    logger.warning(f"Error loading optimized billing program: {e}")
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
    lm = dspy_set_language_model(settings)
    
    try:
        # Check if we're using a TracedReAct or dspy.Predict instance
        if isinstance(billing_optimized, TracedReAct):
            # For TracedReAct, we need to await the result if it's async
            logger.info("Using TracedReAct optimized billing module")
            prediction = billing_optimized(chat_history=chat_history)
            return prediction.final_response
        else:
            # For dspy.Predict, we can call directly
            logger.info("Using dspy.Predict billing module")
            prediction = billing_optimized(chat_history=chat_history)
            return prediction.final_response
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