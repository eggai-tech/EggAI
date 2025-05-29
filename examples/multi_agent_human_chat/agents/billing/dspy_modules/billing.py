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


# Initialize tracer
tracer = create_tracer("billing_agent")

# Path to the SIMBA optimized JSON file
optimized_model_path = Path(__file__).resolve().parent / "optimized_billing_simba.json"

# Create base model with tracing that we'll use
billing_model = TracedReAct(
    BillingSignature,
    tools=[get_billing_info, update_billing_info],
    name="billing_react",
    tracer=tracer,
    max_iters=5,
)

# Flag to indicate if we're using optimized prompts (from JSON)
using_optimized_prompts = False

# Try to load prompts from the optimized JSON file directly
if optimized_model_path.exists():
    try:
        import json

        logger.info(f"Loading optimized prompts from {optimized_model_path}")
        with open(optimized_model_path, "r") as f:
            optimized_data = json.load(f)

            # Check if the JSON has the expected structure
            if "react" in optimized_data and "signature" in optimized_data["react"]:
                # Extract the optimized instructions
                optimized_instructions = optimized_data["react"]["signature"].get(
                    "instructions"
                )
                if optimized_instructions:
                    logger.info("Successfully loaded optimized instructions")
                    # Update the instructions in our signature class
                    BillingSignature.__doc__ = optimized_instructions
                    using_optimized_prompts = True

            if not using_optimized_prompts:
                logger.warning(
                    "Optimized JSON file exists but doesn't have expected structure"
                )
    except Exception as e:
        logger.error(f"Error loading optimized JSON: {e}")
else:
    logger.info(f"Optimized model file not found at {optimized_model_path}")

# Log which prompts we're using
logger.info(
    f"Using {'optimized' if using_optimized_prompts else 'standard'} prompts with tracer"
)


@traced_dspy_function(name="billing_dspy")
def billing_optimized_dspy(chat_history: str) -> str:
    """Process a billing inquiry and generate a response."""
    # Initialize language model
    dspy_set_language_model(settings)

    # Validate input
    if not chat_history or len(chat_history.strip()) < 5:
        logger.warning("Empty or too short chat history")
        raise ValueError("Chat history is too short")

    # Process with model (uses the optimized prompts if available)
    logger.info(
        f"Processing with {'optimized' if using_optimized_prompts else 'standard'} prompts"
    )
    prediction = billing_model(chat_history=chat_history)

    # Return final response
    return prediction.final_response
