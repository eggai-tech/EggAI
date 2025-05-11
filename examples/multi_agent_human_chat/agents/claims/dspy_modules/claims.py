"""Claims Agent optimized DSPy module for production use."""
import json
import os
import time
from pathlib import Path
from typing import Any, Dict, Optional

import dspy
from pydantic import BaseModel, Field

from agents.claims.config import settings
from libraries.dspy_set_language_model import dspy_set_language_model
from libraries.logger import get_console_logger
from libraries.tracing import TracedReAct, create_tracer, traced_dspy_function

logger = get_console_logger("claims_agent.dspy")


class ModelConfig(BaseModel):
    """Configuration for the claims DSPy model."""
    name: str = Field("claims_react", description="Name of the model")
    max_iterations: int = Field(5, description="Maximum iterations for the model", ge=1, le=10)
    use_tracing: bool = Field(True, description="Whether to trace model execution")
    cache_enabled: bool = Field(False, description="Whether to enable model caching")
    truncation_length: int = Field(15000, description="Maximum length for conversation history", ge=1000)

DEFAULT_CONFIG = ModelConfig()



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

    TOOLS:
    - get_claim_status(claim_number: str) -> str:
        Retrieves the current status, payment estimate, next steps, and any outstanding items for a given claim. Returns JSON string.
    - file_claim(policy_number: str, claim_details: str) -> str:
        Creates a new claim under the customer's policy with the provided incident details. Returns JSON string of new claim.
    - update_claim_info(claim_number: str, field: str, new_value: str) -> str:
        Modifies a specified field (e.g., "address", "phone", "damage_description") on an existing claim. Returns JSON string of updated claim.

    RESPONSE FORMAT:
    - Respond in a clear, courteous, and professional tone.
    - Summarize the key information or confirm the action taken.
    - Example for status inquiry:
        "Your claim #123456 is currently 'In Review'. We estimate a payout of $2,300 by 2025-05-15. We're still awaiting your repair estimates—please submit them at your earliest convenience."
    - Example for filing a claim:
        "I've filed a new claim #789012 under policy ABC-123. Please upload photos of the damage and any police report within 5 business days to expedite processing."

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

def load_optimized_signature() -> Optional[type]:
    """Load the optimized signature from JSON file if available."""
    json_path = Path(__file__).resolve().parent / "optimized_claims.json"
    
    if not os.path.exists(json_path):
        logger.warning(f"No optimized signature file found at {json_path}")
        return None
    
    try:
        with open(str(json_path), 'r') as f:
            data = json.load(f)
        
        if "instructions" in data:
            # Create optimized signature subclass
            class OptimizedClaimsSignature(ClaimsSignature):
                """Optimized signature based on ClaimsSignature."""
                pass
            
            OptimizedClaimsSignature.__doc__ = data["instructions"]
            logger.info("Successfully loaded optimized claims signature")
            return OptimizedClaimsSignature
            
        return None
    
    except Exception as e:
        logger.error(f"Error loading optimized signature: {e}")
        return None


# Create the claims model
signature_class = load_optimized_signature() or ClaimsSignature
claims_optimized = TracedReAct(
    signature_class,
    tools=[get_claim_status, file_claim, update_claim_info],
    name="claims_react_optimized",
    tracer=claims_tracer,
    max_iters=5,
)


def get_prediction_from_model(model, chat_history: str):
    """Get prediction from a DSPy model."""
    with claims_tracer.start_as_current_span("get_prediction_from_model") as span:
        span.set_attribute("chat_history_length", len(chat_history) if chat_history else 0)
        
        if not chat_history:
            raise ValueError("Empty chat history provided to prediction model")
        
        model_type = type(model).__name__
        span.set_attribute("model_type", model_type)
        
        start_time = time.perf_counter()
        
        logger.info(f"Using {model_type} for prediction")
        prediction = model(chat_history=chat_history)
        
        elapsed = time.perf_counter() - start_time
        span.set_attribute("prediction_time_ms", elapsed * 1000)
        span.set_attribute("response_length", len(prediction.final_response))
        
        return prediction


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
    
    # Perform truncation
    lines = chat_history.split('\n')
    truncated_lines = lines[-30:]  # Keep last 30 lines
    truncated_history = '\n'.join(truncated_lines)
    
    # Update result
    result["history"] = truncated_history
    result["truncated"] = True
    result["truncated_length"] = len(truncated_history)
    
    return result


@traced_dspy_function(name="claims_dspy")
def claims_optimized_dspy(chat_history: str, config: Optional[ModelConfig] = None) -> str:
    """Process a claims inquiry using the DSPy model."""
    config = config or DEFAULT_CONFIG
        
    with claims_tracer.start_as_current_span("claims_optimized_dspy") as span:
        span.set_attribute("input_length", len(chat_history))
        start_time = time.perf_counter()
        
        # Initialize language model
        dspy_set_language_model(settings, overwrite_cache_enabled=config.cache_enabled)
        
        # Handle long conversations
        truncation_result = truncate_long_history(chat_history, config)
        chat_history = truncation_result["history"]
        
        # Record truncation if needed
        if truncation_result["truncated"]:
            span.set_attribute("truncated", True)
            span.set_attribute("original_length", truncation_result["original_length"])
            span.set_attribute("truncated_length", truncation_result["truncated_length"])
        
        # Get prediction directly from model
        prediction = claims_optimized(chat_history=chat_history)
        response = prediction.final_response
        
        if not response or len(response) < 10:
            raise ValueError("Model returned an empty or too short response")
            
        # Record metrics
        elapsed = time.perf_counter() - start_time    
        span.set_attribute("processing_time_ms", elapsed * 1000)
        span.set_attribute("response_length", len(response))
        
        return response


if __name__ == "__main__":
    # Test the claims DSPy module
    test_conversation = (
        "User: Hi, I'd like to check my claim status.\n"
        "ClaimsAgent: Sure! Could you please provide your claim number?\n"
        "User: It's 1001.\n"
    )
    
    result = claims_optimized_dspy(test_conversation)
    print(f"Response: {result}")