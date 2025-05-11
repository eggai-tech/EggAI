"""Billing Agent DSPy module for policy information and updates."""
import json
import os
from pathlib import Path

import dspy

from agents.billing.config import settings
from agents.billing.dspy_modules.billing_data import (
    get_billing_info,
    update_billing_info,
)
from libraries.dspy_set_language_model import dspy_set_language_model
from libraries.logger import get_console_logger
from libraries.tracing import TracedReAct, create_tracer, traced_dspy_function

logger = get_console_logger("billing_agent.dspy")


class BillingSignature(dspy.Signature):
    """
    You are the Billing Agent for an insurance company.

    ROLE:
      - Assist customers with billing inquiries such as amounts, billing cycles, and payment status
      - Retrieve or update billing information when provided a policy number
      - Provide concise, helpful responses

    TOOLS:
      - get_billing_info(policy_number): Retrieves billing information
      - update_billing_info(policy_number, field, new_value): Updates billing fields

    RESPONSE FORMAT:
      - For balance inquiries: "Your current amount due is $X.XX with a due date of YYYY-MM-DD. Your status is 'Status'."
      - For payment info: "Your next payment of $X.XX is due on YYYY-MM-DD, and your current status is 'Status'."
      - For billing cycle: "Your current billing cycle is 'Cycle' with the next payment of $X.XX due on YYYY-MM-DD."

    GUIDELINES:
      - Use a professional, helpful tone
      - Always require a policy number before providing account details
      - Never reveal billing information without an explicit policy number
      - Use YYYY-MM-DD date format
      - Match response format to query type
    """

    chat_history: str = dspy.InputField(desc="Full conversation context.")
    final_response: str = dspy.OutputField(desc="Billing response to the user.")


def load_optimized_signature():
    """Load the optimized signature from JSON file."""
    json_path = Path(__file__).resolve().parent / "optimized_billing.json"
    
    if not os.path.exists(json_path):
        logger.warning(f"No optimized signature file found at {json_path}")
        return None
    
    try:
        with open(str(json_path), 'r') as f:
            signature_data = json.load(f)
        
        if "instructions" in signature_data:
            from dataclasses import dataclass
            
            @dataclass
            class OptimizedBillingSignature(BillingSignature):
                """Optimized signature for the billing agent."""
                pass
            
            OptimizedBillingSignature.__doc__ = signature_data["instructions"]
            
            logger.info("Successfully loaded optimized billing signature")
            return OptimizedBillingSignature
            
        return None
    
    except Exception as e:
        logger.error(f"Error loading optimized signature: {e}")
        return None


# Create the DSPy model
tracer = create_tracer("billing_agent")
signature_class = load_optimized_signature() or BillingSignature
billing_model = TracedReAct(
    signature_class,
    tools=[get_billing_info, update_billing_info],
    name="billing_react",
    tracer=tracer,
    max_iters=5,
)


@traced_dspy_function(name="billing_dspy")
def billing_optimized_dspy(chat_history: str) -> str:
    """Process a billing inquiry and generate a response."""
    lm = dspy_set_language_model(settings)
    prediction = billing_model(chat_history=chat_history)
    
    return prediction.final_response