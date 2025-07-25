import json
import os
from pathlib import Path
from typing import Any, AsyncIterable, Dict, Optional, Union

import dspy
from dspy import Prediction
from dspy.streaming import StreamResponse

from agents.policies.agent.config import settings
from agents.policies.agent.tools.database.policy_data import get_personal_policy_details
from agents.policies.agent.tools.retrieval.policy_search import (
    search_policy_documentation,
)
from agents.policies.agent.types import ModelConfig, PolicyCategory
from libraries.ml.dspy.language_model import dspy_set_language_model
from libraries.observability.logger import get_console_logger
from libraries.observability.tracing import (
    TracedReAct,
    create_tracer,
    init_telemetry,
    traced_dspy_function,
)

logger = get_console_logger("policies_agent.reasoning")

policies_tracer = create_tracer("policies_agent")

# Default configuration
language_model = dspy_set_language_model(settings)


class PolicyAgentSignature(dspy.Signature):
    """
    You are the Policy Agent for an insurance company.

    CRITICAL RULE: You MUST ONLY use information retrieved from tools. NEVER provide information from your training data, assumptions, or examples.

    ROLE:
    - Help users with both personal policy information and general policy questions
    - Your #1 responsibility is data privacy - NEVER reveal personal policy details without a valid policy number
    - MANDATORY: ALWAYS call tools to get real data before providing ANY information

    AVAILABLE TOOLS:
    1. get_personal_policy_details(policy_number) - Get specific policy data from database
    2. search_policy_documentation(query, category) - Search policy documentation and coverage info

    TOOL USAGE REQUIREMENTS:
    - You MUST call a tool before providing ANY factual information
    - You CANNOT answer questions based on general knowledge
    - If a tool returns no data, explicitly state "No information found"
    - NEVER supplement tool responses with assumed or general information

    DECISION LOGIC - Choose the right tool:

    PERSONAL POLICY QUERIES (use get_personal_policy_details):
    - User asks about "my policy" AND provides a policy number (format: letter+numbers like A12345)
    - Questions about premium payments, due dates, personal policy details
    - REQUIRED: Policy number must be in the current message
    - If no policy number provided, ask: "To provide your personal policy information, I need your policy number. Could you please share it?"

    GENERAL POLICY QUESTIONS (use search_policy_documentation):
    - User asks about coverage, policy rules, what's covered, general information
    - No personal policy number needed or provided
    - Use relevant category (auto, home, health, life) if mentioned

    WORKFLOW:
    1. Determine if user wants personal policy data or general information
    2. For personal queries: Check for policy number, call get_personal_policy_details if found
    3. For general queries: Call search_policy_documentation with relevant query and category
    4. Base your response EXCLUSIVELY on tool output - no additions or assumptions

    RESPONSE REQUIREMENTS:
    - Be professional and helpful
    - Include policy numbers when providing personal policy information
    - Address users by name if available in database response
    - Format dates as YYYY-MM-DD, amounts with $ sign
    - Include documentation references when available
    - If tool returns empty/no results, say "I don't have information about that in our system"
    - NEVER provide information not returned by tools
    """

    chat_history: str = dspy.InputField(desc="Full conversation context.")

    policy_category: Optional[PolicyCategory] = dspy.OutputField(
        desc="Policy category if identified."
    )
    policy_number: Optional[str] = dspy.OutputField(
        desc="Policy number if provided by user."
    )
    documentation_reference: Optional[str] = dspy.OutputField(
        desc="Reference on the documentation if found (e.g. Section 3.1)."
    )

    final_response: str = dspy.OutputField(desc="Final response message to the user.")


# Path to the SIMBA optimized JSON file
optimized_model_path = (
    Path(__file__).resolve().parent / "optimization" / "optimized_policies_simba.json"
)

policies_model = TracedReAct(
    PolicyAgentSignature,
    tools=[get_personal_policy_details, search_policy_documentation],
    name="policies_react",
    tracer=policies_tracer,
    max_iters=5,
)

# Flag to indicate if we're using optimized prompts (from JSON)
using_optimized_prompts = False

# Try to load prompts from the optimized JSON file directly
if (
    optimized_model_path.exists()
    and os.environ.get("POLICIES_USE_OPTIMIZED_PROMPTS", "false").lower() == "true"
):
    try:
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
                    PolicyAgentSignature.__doc__ = optimized_instructions
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
    f"Using {'optimized' if using_optimized_prompts else 'standard'} prompts for policies agent"
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

    # Check if truncation needed based on both character count and line count
    lines = chat_history.split("\n")
    max_lines = 30
    
    if len(chat_history) <= max_length and len(lines) <= max_lines:
        return result

    truncated_lines = lines[-max_lines:]  # Keep last 30 lines
    truncated_history = "\n".join(truncated_lines)

    # Update result
    result["history"] = truncated_history
    result["truncated"] = True
    result["truncated_length"] = len(truncated_history)

    return result


@traced_dspy_function(name="process_policies")
def process_policies(
    chat_history: str, config: Optional[ModelConfig] = None
) -> AsyncIterable[Union[StreamResponse, Prediction]]:
    """Process a policies inquiry using the DSPy ReAct model with streaming output."""
    config = config or ModelConfig()

    # Handle long conversations
    truncation_result = truncate_long_history(chat_history, config)
    chat_history = truncation_result["history"]

    return dspy.streamify(
        policies_model,
        stream_listeners=[
            dspy.streaming.StreamListener(signature_field_name="final_response"),
        ],
        include_final_prediction_in_output_stream=True,
        is_async_program=False,
        async_streaming=True,
    )(chat_history=chat_history)


if __name__ == "__main__":
    import asyncio

    async def run():
        init_telemetry(settings.app_name, endpoint=settings.otel_endpoint)

        # Test the policies DSPy module
        test_conversation = (
            "User: I need information about my policy.\n"
            "PoliciesAgent: Sure, I can help with that. Could you please provide me with your policy number?\n"
            "User: My policy number is A12345\n"
        )

        chunks = process_policies(test_conversation)

        async for chunk in chunks:
            if isinstance(chunk, StreamResponse):
                print(f"Stream chunk: {chunk.chunk}")
            elif isinstance(chunk, Prediction):
                result = chunk
                print(f"Final response: {result.final_response}")
                if result.policy_category:
                    print(f"Policy category: {result.policy_category}")
                if result.policy_number:
                    print(f"Policy number: {result.policy_number}")
                if result.documentation_reference:
                    print(f"Documentation reference: {result.documentation_reference}")

    asyncio.run(run())
