"""Claims Agent optimized DSPy module for production use."""
import json
import os
from pathlib import Path

import dspy

from agents.claims.config import settings
from libraries.dspy_set_language_model import dspy_set_language_model
from libraries.logger import get_console_logger
from libraries.tracing import TracedReAct, traced_dspy_function

logger = get_console_logger("claims_agent.dspy")


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
    - Do not disclose internal processes or irrelevant details.
    - Keep answers concise—focus only on what the customer needs to know or do next.
    - Always confirm changes you make:
        "I've updated your mailing address on claim #123456 as requested."

    Input Fields:
    - chat_history: str — Full conversation context.

    Output Fields:
    - final_response: str — Claims response to the user.
    """

    chat_history: str = dspy.InputField(desc="Full conversation context.")
    final_response: str = dspy.OutputField(desc="Claims response to the user.")


# Try to load the optimized program or use base version
try:
    json_path = Path(__file__).resolve().parent / "optimized_claims.json"
    if os.path.exists(json_path):
        logger.info(f"Loading optimized TracedReAct claims program from {json_path}")
        # Create TracedReAct with real tools
        from agents.claims.dspy_modules.claims_data import (
            file_claim,
            get_claim_status,
            update_claim_info,
        )
        from libraries.tracing import create_tracer
        
        tracer = create_tracer("claims_agent_optimized")
        try:
            # Try standard loading method first
            claims_signature = TracedReAct.load_signature(str(json_path))
            claims_optimized = TracedReAct(
                claims_signature,
                tools=[get_claim_status, file_claim, update_claim_info],
                name="claims_react_optimized",
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
                class ClaimsCustomSignature(ClaimsSignature):
                    pass
                
                # Set custom instructions if available
                if "instructions" in signature_data:
                    instructions = signature_data["instructions"]
                    # Ensure date formatting instructions are included
                    if "IMPORTANT: Dates MUST be in the format YYYY-MM-DD" not in instructions:
                        instructions += "\n    IMPORTANT: Dates MUST be in the format YYYY-MM-DD. For example, use \"2025-03-15\" instead of \"March 15th, 2025\"."
                    ClaimsCustomSignature.__doc__ = instructions
                
                # Create a new TracedReAct with the custom signature
                claims_optimized = TracedReAct(
                    ClaimsCustomSignature,
                    tools=[get_claim_status, file_claim, update_claim_info],
                    name="claims_react_optimized",
                    tracer=tracer,
                    max_iters=5,
                )
                
                logger.info("Successfully loaded from simplified JSON format")
            except Exception as json_load_error:
                logger.error(f"Simplified JSON loading also failed: {json_load_error}")
                raise
    else:
        logger.warning(f"Optimized claims program not found at {json_path}, using base version")
        claims_optimized = dspy.Predict(ClaimsSignature)
except Exception as e:
    logger.warning(f"Error loading optimized claims program: {e}")
    claims_optimized = dspy.Predict(ClaimsSignature)


@traced_dspy_function(name="claims_dspy")
def claims_optimized_dspy(chat_history: str) -> str:
    """
    Process a claims inquiry using the optimized DSPy program.
    
    Args:
        chat_history: The conversation history.
        
    Returns:
        str: The claims agent's response.
    """
    lm = dspy_set_language_model(settings)
    
    try:
        # Check if we're using a TracedReAct or dspy.Predict instance
        if isinstance(claims_optimized, TracedReAct):
            # For TracedReAct, we need to await the result if it's async
            logger.info("Using TracedReAct optimized claims module")
            prediction = claims_optimized(chat_history=chat_history)
            return prediction.final_response
        else:
            # For dspy.Predict, we can call directly
            logger.info("Using dspy.Predict claims module")
            prediction = claims_optimized(chat_history=chat_history)
            return prediction.final_response
    except Exception as e:
        logger.error(f"Error in claims_optimized_dspy: {e}")
        return "I apologize, but I'm having trouble processing your request right now. Could you please provide more details about your claim inquiry?"


if __name__ == "__main__":
    # Test the claims DSPy module
    test_conversation = (
        "User: Hi, I'd like to check my claim status.\n"
        "ClaimsAgent: Sure! Could you please provide your claim number?\n"
        "User: It's 1001.\n"
    )
    
    result = claims_optimized_dspy(test_conversation)
    print(f"Response: {result}")