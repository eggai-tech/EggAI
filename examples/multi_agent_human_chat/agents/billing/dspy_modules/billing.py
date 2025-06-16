from pathlib import Path
from typing import Any, AsyncIterable, Dict, Optional, Union

import dspy
from dspy import Prediction
from dspy.streaming import StreamResponse

from agents.billing.config import settings
from agents.billing.dspy_modules.billing_data import (
    get_billing_info,
    update_billing_info,
)
from agents.billing.types import ModelConfig
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


def truncate_long_history(
    chat_history: str, config: Optional[ModelConfig] = None
) -> Dict[str, Any]:
    """Truncate conversation history if it exceeds maximum length."""
    config = config or ModelConfig()
    max_length = config.truncation_length

    result = {
        "history": chat_history,
        "truncated": False,
        "original_length": len(chat_history),
        "truncated_length": len(chat_history),
    }

    # Check if truncation needed
    if len(chat_history) <= max_length:
        return result

    # Perform truncation - keep the last 30 lines like the other agents
    lines = chat_history.split("\n")
    truncated_lines = lines[-30:]  # Keep last 30 lines
    truncated_history = "\n".join(truncated_lines)

    # Update result
    result["history"] = truncated_history
    result["truncated"] = True
    result["truncated_length"] = len(truncated_history)

    return result


@traced_dspy_function(name="billing_dspy")
async def billing_optimized_dspy(
    chat_history: str, config: Optional[ModelConfig] = None
) -> AsyncIterable[Union[StreamResponse, Prediction]]:
    """Process a billing inquiry using the DSPy model with streaming output."""
    config = config or ModelConfig()

    # Handle long conversations
    truncation_result = truncate_long_history(chat_history, config)
    chat_history = truncation_result["history"]

    # Create a streaming version of the billing model
    streamify_func = dspy.streamify(
        billing_model,
        stream_listeners=[
            dspy.streaming.StreamListener(signature_field_name="final_response"),
        ],
        include_final_prediction_in_output_stream=True,
        is_async_program=False,
        async_streaming=True,
    )

    async for chunk in streamify_func(chat_history=chat_history):
        yield chunk


if __name__ == "__main__":

    async def run():
        from libraries.tracing import init_telemetry

        init_telemetry(settings.app_name)

        # Test the billing DSPy module
        test_conversation = (
            "User: How much is my premium?\n"
            "BillingAgent: Could you please provide your policy number?\n"
            "User: It's B67890.\n"
        )

        logger.info("Running test query for billing agent")
        chunks = billing_optimized_dspy(test_conversation)

        async for chunk in chunks:
            if isinstance(chunk, StreamResponse):
                print(f"Stream chunk: {chunk.chunk}")
            elif isinstance(chunk, Prediction):
                result = chunk
                print(f"Final response: {result.final_response}")

    import asyncio

    asyncio.run(run())
