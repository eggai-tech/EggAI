import json
import time
from pathlib import Path
from typing import Any, AsyncIterable, Dict, Optional, Union

import dspy
from dspy import Prediction
from dspy.streaming import StreamResponse

from agents.claims.config import settings
from agents.claims.types import ModelConfig
from libraries.ml.dspy.language_model import dspy_set_language_model
from libraries.observability.logger import get_console_logger
from libraries.observability.tracing import (
    TracedReAct,
    create_tracer,
    traced_dspy_function,
)
from libraries.observability.tracing.otel import safe_set_attribute

logger = get_console_logger("claims_agent.dspy")


DEFAULT_CONFIG = ModelConfig(name="claims_react")


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
    - Your #1 responsibility is data privacy and security
    - NEVER reveal, guess, or make up ANY claim information without explicit claim numbers
    - When a user asks about claim status without providing a claim number, ALWAYS respond ONLY with:
      "I need a valid claim number to check the status of your claim. Could you please provide it?"

    RESPONSE FORMAT:
    - Respond in a clear, courteous, and professional tone.
    - Summarize the key information or confirm the action taken.
    - Example for status inquiry:
        "Your claim #123456 is currently 'In Review'. We estimate a payout of $2,300 by 2026-05-15. We're still awaiting your repair estimates—please submit them at your earliest convenience."
    - Example for filing a claim:
        "I've filed a new claim #789012 under policy ABC-123. Please email photos of the damage and any police report to claims@example.com within 5 business days to expedite processing."

    GUIDELINES:
    - Only invoke a tool when the user provides or requests information that requires it (a claim number for status, policy number and details to file, etc.).
    - If the user hasn't specified a claim or policy number when needed, politely request it:
        "Could you please provide your claim number so I can check its status?"
    - For update requests, follow these steps carefully:
        1. First ask for the claim number if not provided
        2. Then ask for the specific information to update
        3. Only call update_claim_info after both claim number AND the new information are provided
    - When the user wants to update an address, ALWAYS respond with: "What is the new address you'd like to update on your claim?"
    - When the user wants to update a phone number, ALWAYS respond with: "What is the new phone number you'd like to update on your claim?"
    - Do not disclose internal processes or irrelevant details.
    - Keep answers concise—focus only on what the customer needs to know or do next.
    - Always confirm changes you make:
        "I've updated your mailing address on claim #123456 as requested."

    CRITICAL PRIVACY PROTECTION:
    - NEVER guess, invent, or assume claim numbers - they must be EXPLICITLY provided by the user
    - NEVER use example claim numbers from your instructions (like #123456) as if they were real
    - NEVER use or recognize claim details from previous conversation turns - each request must include its own claim number
    - When a user says something like "I want to check my claim status" WITHOUT a claim number, respond ONLY with:
      "I need a valid claim number to check the status of your claim. Could you please provide it?"
    - NEVER reveal ANY claim information unless the user has provided a specific, valid claim number in their CURRENT message

    CRITICAL WORKFLOW FOR UPDATING INFORMATION:
    - If a user message contains both "update" and "address" or "phone", and includes a claim number, but does NOT include a new value, respond: "What is the new [field] you'd like to update on your claim?"
    - Do NOT call update_claim_info until you have BOTH the claim number AND the new value
    - Example sequence:
      User: "I need to update my address on my claim."
      Agent: "I can help with that. What is your claim number?"
      User: "Claim number 1002."
      Agent: "What is the new address you'd like to update on your claim?"
      User: "123 New Street, City, State, ZIP"
      Agent: [Now call update_claim_info with claim number and new address]

    CRITICAL CLAIM STATUS WORKFLOW:
    - When a user asks about claim status:
      1. FIRST STEP: Check their CURRENT message for a claim number
      2. If NO valid claim number is found IN THE CURRENT MESSAGE, respond ONLY with:
         "I need a valid claim number to check the status of your claim. Could you please provide it?"
      3. NEVER proceed beyond this point if there is no claim number in the current message
      4. NEVER look at previous messages for claim numbers - they must be provided in the current message
      5. NEVER guess or infer claim numbers - they must be explicitly provided by the user
      6. Only use get_claim_status AFTER confirming a valid claim number exists in the current message

    CRITICAL WORKFLOW FOR FILING NEW CLAIMS:
    - When a user wants to file a new claim:
      1. Check if the user provided a policy number and details about the incident
      2. If BOTH policy number AND incident details are provided in the current message, use file_claim tool ONCE to create the new claim
      3. Call the file_claim tool ONLY ONCE, never multiple times for the same request
      4. NEVER ask for more information when both policy number and incident details are already provided

    Input Fields:
    - chat_history: str — Full conversation context.

    Output Fields:
    - final_response: str — Claims response to the user.
    """

    chat_history: str = dspy.InputField(desc="Full conversation context.")
    final_response: str = dspy.OutputField(desc="Claims response to the user.")


# Import needed tools for the claims agent
from agents.claims.dspy_modules.claims_data import (
    file_claim,
    get_claim_status,
    update_claim_info,
)

# Create tracer for the optimized claims module
claims_tracer = create_tracer("claims_agent_optimized")

# Create base model with tracing that we'll use
claims_optimized = TracedReAct(
    ClaimsSignature,
    tools=[get_claim_status, file_claim, update_claim_info],
    name="claims_react",
    tracer=claims_tracer,
    max_iters=5,
)


def load_optimized_prompts() -> bool:
    """Load optimized instructions from SIMBA JSON, updating ClaimsSignature doc.

    Returns:
        bool: True if optimized prompts were loaded, False otherwise.
    """
    optimized_model_path = Path(__file__).resolve().parent / "optimized_claims_simba.json"
    using_optimized = False

    if optimized_model_path.exists():
        try:
            logger.info(f"Loading optimized prompts from {optimized_model_path}")
            with open(optimized_model_path, "r") as f:
                data = json.load(f)

            instr = (
                data.get("react", {}).get("signature", {}).get("instructions")
            )
            if instr:
                ClaimsSignature.__doc__ = instr
                using_optimized = True
                logger.info("Successfully loaded optimized instructions")
            else:
                logger.warning(
                    "Optimized JSON exists but missing 'react.signature.instructions'"
                )
        except Exception as e:
            logger.error(f"Error loading optimized JSON: {e}")
    else:
        logger.info(f"Optimized model file not found at {optimized_model_path}")

    mode = 'optimized' if using_optimized else 'standard'
    logger.info(f"Using {mode} prompts with tracer")
    return using_optimized


def get_prediction_from_model(model, chat_history: str):
    """Get prediction from a DSPy model."""
    with claims_tracer.start_as_current_span("get_prediction_from_model") as span:
        safe_set_attribute(
            span, "chat_history_length", len(chat_history) if chat_history else 0
        )

        if not chat_history:
            raise ValueError("Empty chat history provided to prediction model")

        model_type = type(model).__name__
        safe_set_attribute(span, "model_type", model_type)

        start_time = time.perf_counter()

        logger.info(f"Using {model_type} for prediction")
        prediction = model(chat_history=chat_history)

        elapsed = time.perf_counter() - start_time
        safe_set_attribute(span, "prediction_time_ms", elapsed * 1000)
        safe_set_attribute(span, "response_length", len(prediction.final_response))

        return prediction


def truncate_long_history(
    chat_history: str, config: Optional[ModelConfig] = None
) -> Dict[str, Any]:
    """Truncate conversation history if it exceeds maximum length."""
    config = config or DEFAULT_CONFIG
    max_length = config.truncation_length

    result = {
        "history": chat_history,
        "truncated": False,
        "original_length": len(chat_history),
        "truncated_length": len(chat_history),
    }

    if len(chat_history) <= max_length:
        return result

    # Perform truncation
    lines = chat_history.split("\n")
    truncated_lines = lines[-30:]  # Keep last 30 lines
    truncated_history = "\n".join(truncated_lines)

    # Update result
    result["history"] = truncated_history
    result["truncated"] = True
    result["truncated_length"] = len(truncated_history)

    return result


@traced_dspy_function(name="claims_dspy")
async def process_claims(
    chat_history: str, config: Optional[ModelConfig] = None
) -> AsyncIterable[Union[StreamResponse, Prediction]]:
    """Process a claims inquiry using the DSPy model with streaming output."""
    config = config or DEFAULT_CONFIG

    # Handle long conversations
    truncation_result = truncate_long_history(chat_history, config)
    chat_history = truncation_result["history"]

    # Create a streaming version of the claims model
    streamify_func = dspy.streamify(
        claims_optimized,
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
        from libraries.observability.tracing import init_telemetry

        init_telemetry(settings.app_name, endpoint=settings.otel_endpoint)
        # Initialize the DSPy model with the configured language model
        dspy_set_language_model(settings)

        # Test the claims DSPy module
        test_conversation = (
            "User: Hi, I'd like to check my claim status.\n"
            "ClaimsAgent: Sure! Could you please provide your claim number?\n"
            "User: It's 1001.\n"
        )

        chunks = process_claims(test_conversation)

        async for chunk in chunks:
            if isinstance(chunk, StreamResponse):
                print(f"Stream chunk: {chunk.chunk}")
            elif isinstance(chunk, Prediction):
                result = chunk
                print(f"Final response: {result.final_response}")

    import asyncio

    asyncio.run(run())
