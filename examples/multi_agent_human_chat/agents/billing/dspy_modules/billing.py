from pathlib import Path
from typing import Any, AsyncIterable, Dict, Optional, Union

import dspy
from dspy import Prediction
from dspy.streaming import StreamResponse

from agents.billing.config import settings
from agents.billing.types import ModelConfig
from libraries.logger import get_console_logger
from libraries.tracing import TracedReAct, create_tracer

from .billing_data import (
    get_billing_info,
    update_billing_info,
)

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


import json


def load_optimized_instructions(path: Path) -> Optional[str]:
    """
    Load optimized instructions from a JSON file and return them if valid.
    """
    if not path.exists():
        logger.info(f"Optimized model file not found at {path}")
        return None

    try:
        logger.info(f"Loading optimized prompts from {path}")
        with path.open("r") as f:
            data = json.load(f)

        react = data.get("react", {})
        signature = react.get("signature", {})
        instructions = signature.get("instructions")

        if instructions:
            logger.info(f"Successfully loaded optimized instructions from {path}")
            return instructions

        logger.warning(
            "Optimized JSON file exists but missing 'react.signature.instructions'"
        )
    except Exception as e:
        logger.error(f"Error loading optimized JSON: {e}", exc_info=True)

    return None


# Global variables for lazy initialization
tracer = None
_billing_model = None
_initialized = False


def _initialize_billing_model():
    """Lazy initialization of billing model to avoid hanging during imports."""
    global tracer, _billing_model, _initialized
    
    if _initialized:
        return _billing_model
    
    tracer = create_tracer("billing_agent")
    
    # Load optimized instructions if available
    optimized_path = Path(__file__).resolve().parent / "optimized_billing_simba.json"
    instructions = load_optimized_instructions(optimized_path)
    using_optimized_prompts = False
    if instructions:
        BillingSignature.__doc__ = instructions
        using_optimized_prompts = True
    
    _billing_model = TracedReAct(
        BillingSignature,
        tools=[get_billing_info, update_billing_info],
        name="billing_react",
        tracer=tracer,
        max_iters=5,
    )
    
    logger.info(
        f"Using {'optimized' if using_optimized_prompts else 'standard'} prompts with tracer"
    )
    
    _initialized = True
    return _billing_model


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

    if len(chat_history) <= max_length:
        return result

    lines = chat_history.split("\n")
    truncated_lines = lines[-30:]
    truncated_history = "\n".join(truncated_lines)

    result["history"] = truncated_history
    result["truncated"] = True
    result["truncated_length"] = len(truncated_history)

    return result


async def process_billing(
    chat_history: str, config: Optional[ModelConfig] = None
) -> AsyncIterable[Union[StreamResponse, Prediction]]:
    """Process a billing inquiry using the DSPy model with streaming output."""
    config = config or ModelConfig()

    truncation_result = truncate_long_history(chat_history, config)
    chat_history = truncation_result["history"]

    # Get the billing model (lazy initialization)
    billing_model = _initialize_billing_model()

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

        init_telemetry(settings.app_name, endpoint=settings.otel_endpoint)

        test_conversation = (
            "User: How much is my premium?\n"
            "BillingAgent: Could you please provide your policy number?\n"
            "User: It's B67890.\n"
        )

        logger.info("Running test query for billing agent")
        chunks = process_billing(test_conversation)

        async for chunk in chunks:
            if isinstance(chunk, StreamResponse):
                print(f"Stream chunk: {chunk.chunk}")
            elif isinstance(chunk, Prediction):
                result = chunk
                print(f"Final response: {result.final_response}")

    import asyncio

    asyncio.run(run())
