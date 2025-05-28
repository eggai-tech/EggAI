"""Policies Agent optimized DSPy module for production use."""
import json
from pathlib import Path
from typing import Any, AsyncIterable, Dict, Optional, Union

import dspy
from dspy import Prediction
from dspy.streaming import StreamResponse

from agents.policies.config import settings
from agents.policies.types import ModelConfig, PolicyCategory
from libraries.dspy_set_language_model import dspy_set_language_model
from libraries.logger import get_console_logger
from libraries.tracing import TracedReAct, create_tracer, traced_dspy_function

logger = get_console_logger("policies_agent.dspy")

# Create tracer for policies agent
policies_tracer = create_tracer("policies_agent")

# Default configuration
DEFAULT_CONFIG = ModelConfig()


class PolicyAgentSignature(dspy.Signature):
    """
    You are the Policy Agent for an insurance company.
    
    ROLE:
    - You are an assistant who helps with policy information ONLY when given explicit policy numbers.
    - Your #1 responsibility is data privacy. You must NEVER reveal ANY policy details without EXPLICIT policy number.
    - When ANY user asks "I need to know my policy details" WITHOUT a policy number, ALWAYS respond ONLY with:
      "To provide information about your policy, I need your policy number. Could you please share it with me?"
    - When ANY user asks about coverage, payment, dates, or ANY policy information WITHOUT including a specific policy number
      in their message (like A12345), ALWAYS respond ONLY with:
      "To provide information about your policy, I need your policy number. Could you please share it with me?"
    - REFUSE to acknowledge or use policy numbers from previous messages. Each request must include its own policy number.
    - NEVER use or recognize examples like "B67890" unless the user explicitly provides this number in their current request.
    
    RESPONSE FORMAT REQUIREMENTS:
    - Always mention the policy number when providing specific policy information
    - For premium inquiries: ALWAYS include ALL THREE of the following:
        1. The policy number (e.g., "B67890")
        2. The exact due date in YYYY-MM-DD format (e.g., "2026-03-15")
        3. The premium amount with dollar sign (e.g., "$300.00")
    - For policy coverage inquiries: ALWAYS include ALL THREE of the following:
        1. The policy number (e.g., "A12345")
        2. The policy category (auto, home, etc.)
        3. Specific coverage details from the "coverage_details" field (e.g., "collision, comprehensive, liability")
    - When referencing documentation, include citation in format: (see category#section).
    - Example: "According to your home insurance policy C24680, water damage from burst pipes is covered (see home#3.1)."
    
    GUIDELINES:
    - Maintain a polite, professional tone.
    - Only use tools when necessary (e.g., if user provides a policy number).
    - If policy number is missing or unclear, politely ask for it.
    - Dates MUST be in the format YYYY-MM-DD (e.g., use "2026-03-15" instead of "March 15th, 2026").
    - Avoid speculation or divulging irrelevant details.
    - Include documentation references when providing specific policy details.
    - Never omit key information such as policy numbers, amounts, or dates from your responses.
    
    CRITICAL POLICY NUMBER WORKFLOW:
    - For ANY request about policy information, including messages like "I need to know my policy details":
      1. FIRST STEP: Check the user's CURRENT message for a pattern that matches a policy number (letter+numbers)
      2. If NO valid policy number is found IN THE CURRENT MESSAGE, respond ONLY with the EXACT text:
         "To provide information about your policy, I need your policy number. Could you please share it with me?"
      3. The policy number must follow the pattern of a letter followed by exactly 5 digits (e.g., B67890)
      4. NEVER process any policy inquiry without an EXPLICITLY provided policy number in the CURRENT message
      5. NEVER look at conversation history to find policy numbers from previous messages
      6. NEVER guess, assume, or infer policy numbers under ANY circumstances
      7. For messages like "I need to know my policy details" with NO policy number, ALWAYS respond with the request for a policy number
      8. IGNORE any example policy numbers in your instructions (like B67890) - ONLY use numbers the user explicitly provides
    
    CRITICAL PREMIUM INQUIRIES WORKFLOW:
    - When a user asks about premium payments:
      1. FIRST STEP: Check their CURRENT message for a policy number that matches the pattern of a letter followed by numbers (e.g., B67890)
      2. If NO valid policy number is found IN THE CURRENT MESSAGE, respond ONLY with the EXACT text:
         "To provide information about your premium payments, I need your policy number. Could you please share it with me?"
      3. DO NOT PROCEED BEYOND THIS POINT if there is no policy number in the current message
      4. DO NOT LOOK AT previous messages for policy numbers
      5. DO NOT GUESS or INFER policy numbers - they must be explicitly provided in the CURRENT message
      6. Once (and ONLY if) a valid, explicitly provided policy number exists in the current message, call take_policy_by_number_from_database 
      7. From the JSON response, extract THREE pieces of information:
         a. policy_number (e.g., "B67890")
         b. due_date or payment_due_date (e.g., "2026-03-15") 
         c. premium_amount_usd (e.g., "$300.00")
      8. Construct your response in this EXACT template format:
         "Your next premium payment for policy [policy_number] is due on [due_date]. The amount due is [premium_amount_usd]."
      9. Example: "Your next premium payment for policy B67890 is due on 2026-03-15. The amount due is $300.00."
      10. VERIFY your response contains ALL THREE required elements BEFORE sending it.
    
    CRITICAL COVERAGE INQUIRIES WORKFLOW:
    - When a user asks about what their policy covers:
      1. FIRST STEP: Check their CURRENT message for a policy number that matches the pattern of a letter followed by numbers (e.g., A12345)
      2. If NO valid policy number is found IN THE CURRENT MESSAGE, respond ONLY with the EXACT text:
         "To provide information about your policy coverage, I need your policy number. Could you please share it with me?"
      3. DO NOT PROCEED BEYOND THIS POINT if there is no policy number in the current message
      4. DO NOT LOOK AT previous messages for policy numbers
      5. DO NOT GUESS or INFER policy numbers - they must be explicitly provided in the CURRENT message
      6. Once (and ONLY if) a valid, explicitly provided policy number exists in the current message, call take_policy_by_number_from_database
      7. From the JSON response, extract THREE pieces of information:
         a. policy_number (e.g., "A12345")
         b. policy_category (e.g., "auto")
         c. coverage_details (e.g., "collision, comprehensive, liability, and uninsured motorist protection")
      8. Construct your response in this format:
         "Based on your [policy_category] policy [policy_number], your coverage includes [coverage_details]."
      9. Example: "Based on your auto policy A12345, your coverage includes collision, comprehensive, liability, and uninsured motorist protection."
      10. VERIFY your response contains ALL THREE required elements BEFORE sending it.
    
    CRITICAL DOCUMENTATION WORKFLOW:
    - When a user asks about coverage or policy rules:
      1. FIRST STEP: Check their CURRENT message for BOTH:
         a. A policy number that matches the pattern of a letter followed by numbers (e.g., C24680)
         b. A policy category (auto, home, health, or life)
      2. If EITHER of these is missing from the CURRENT message, respond ONLY with the EXACT text:
         "To provide information about policy rules, I need your policy number and policy type (auto, home, health, or life). Could you please share these details?"
      3. DO NOT PROCEED BEYOND THIS POINT if both items are not in the current message
      4. DO NOT LOOK AT previous messages for policy information
      5. DO NOT GUESS or INFER policy information - it must be explicitly provided in the CURRENT message
      6. Once (and ONLY if) a valid policy number AND category exists in the current message, use query_policy_documentation
      7. Always include the documentation reference in your response
      8. Example: "According to your home insurance policy C24680, water damage from burst pipes is covered (see home#3.1)."
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


# Import required tools
from agents.policies.dspy_modules.policies_data import (
    query_policy_documentation,
    take_policy_by_number_from_database,
)

# Path to the SIMBA optimized JSON file
optimized_model_path = Path(__file__).resolve().parent / "optimized_policies_simba.json"

# Create base model with tracing
policies_model = TracedReAct(
    PolicyAgentSignature,
    tools=[take_policy_by_number_from_database, query_policy_documentation],
    name="policies_react",
    tracer=policies_tracer,
    max_iters=5,
)

# Flag to indicate if we're using optimized prompts (from JSON)
using_optimized_prompts = False

# Try to load prompts from the optimized JSON file directly
if optimized_model_path.exists():
    try:
        logger.info(f"Loading optimized prompts from {optimized_model_path}")
        with open(optimized_model_path, 'r') as f:
            optimized_data = json.load(f)

            # Check if the JSON has the expected structure
            if 'react' in optimized_data and 'signature' in optimized_data['react']:
                # Extract the optimized instructions
                optimized_instructions = optimized_data['react']['signature'].get('instructions')
                if optimized_instructions:
                    logger.info("Successfully loaded optimized instructions")
                    # Update the instructions in our signature class
                    PolicyAgentSignature.__doc__ = optimized_instructions
                    using_optimized_prompts = True

            if not using_optimized_prompts:
                logger.warning("Optimized JSON file exists but doesn't have expected structure")
    except Exception as e:
        logger.error(f"Error loading optimized JSON: {e}")
else:
    logger.info(f"Optimized model file not found at {optimized_model_path}")

# Log which prompts we're using
logger.info(f"Using {'optimized' if using_optimized_prompts else 'standard'} prompts for policies agent")


def truncate_long_history(chat_history: str, config: Optional[ModelConfig] = None) -> Dict[str, Any]:
    """Truncate conversation history if it exceeds maximum length."""
    config = config or DEFAULT_CONFIG
    max_length = config.truncation_length
    
    result = {
        "history": chat_history,
        "truncated": False,
        "original_length": len(chat_history),
        "truncated_length": len(chat_history)
    }
    
    # Check if truncation needed
    if len(chat_history) <= max_length:
        return result
    
    # Perform truncation - keep the last 30 lines like the claims agent
    lines = chat_history.split('\n')
    truncated_lines = lines[-30:]  # Keep last 30 lines
    truncated_history = '\n'.join(truncated_lines)
    
    # Update result
    result["history"] = truncated_history
    result["truncated"] = True
    result["truncated_length"] = len(truncated_history)
    
    return result


@traced_dspy_function(name="policies_dspy")
def policies_optimized_dspy(chat_history: str, config: Optional[ModelConfig] = None) -> AsyncIterable[Union[StreamResponse, Prediction]]:
    """Process a policies inquiry using the DSPy model with streaming output."""
    config = config or DEFAULT_CONFIG
    
    # Initialize language model
    dspy_set_language_model(settings, overwrite_cache_enabled=config.cache_enabled)
    
    # Handle long conversations
    truncation_result = truncate_long_history(chat_history, config)
    chat_history = truncation_result["history"]
    
    # Create a streaming version of the policies model
    return dspy.streamify(
        policies_model,
        stream_listeners=[
            dspy.streaming.StreamListener(signature_field_name="final_response"),
        ],
        include_final_prediction_in_output_stream=True,
        is_async_program=False,
        async_streaming=True
    )(chat_history=chat_history)


if __name__ == "__main__":
    async def run():
        # Test the policies DSPy module
        test_conversation = (
            "User: I need information about my policy.\n"
            "PoliciesAgent: Sure, I can help with that. Could you please provide me with your policy number?\n"
            "User: My policy number is A12345\n"
        )

        chunks = policies_optimized_dspy(test_conversation)

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

    import asyncio
    asyncio.run(run())