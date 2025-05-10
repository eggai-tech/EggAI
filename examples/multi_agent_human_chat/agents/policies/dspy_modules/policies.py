"""Policies Agent optimized DSPy module for production use."""
import json
import os
import time
from pathlib import Path
from typing import Any, Dict, Optional

import dspy

from agents.policies.config import settings
from agents.policies.types import (
    ModelConfig,
    PolicyCategory,
    PolicyResponseData,
)
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
    
    TOOLS:
    - take_policy_by_number_from_database(policy_number): 
        Retrieves policy information including:
        - policy_number: The policy's unique identifier (e.g., "B67890")
        - name: The policyholder's name 
        - policy_category: Type of policy (auto, home, life, health)
        - premium_amount: Numeric amount (e.g., 300)
        - premium_amount_usd: Formatted amount with currency symbol (e.g., "$300.00")
        - due_date: When payment is due in YYYY-MM-DD format (e.g., "2025-03-15")
        - payment_due_date: Alternative field name for the due date
        - next_payment_date: Alternative field name for the due date
        - coverage_details: Specific details about what the policy covers (e.g., "collision, comprehensive, liability")
        
        Always extract and explicitly include the appropriate fields based on the user's question.
        
    - query_policy_documentation(category, query):  
        Searches policy documentation for specific information.
    
    RESPONSE FORMAT REQUIREMENTS:
    - Always mention the policy number when providing specific policy information
    - For premium inquiries: ALWAYS include ALL THREE of the following:
        1. The policy number (e.g., "B67890")
        2. The exact due date in YYYY-MM-DD format (e.g., "2025-03-15")
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
    - Dates MUST be in the format YYYY-MM-DD (e.g., use "2025-03-15" instead of "March 15th, 2025").
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
         b. due_date or payment_due_date (e.g., "2025-03-15") 
         c. premium_amount_usd (e.g., "$300.00")
      8. Construct your response in this EXACT template format:
         "Your next premium payment for policy [policy_number] is due on [due_date]. The amount due is [premium_amount_usd]."
      9. Example: "Your next premium payment for policy B67890 is due on 2025-03-15. The amount due is $300.00."
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


def create_policies_model(config: Optional[ModelConfig] = None) -> TracedReAct:
    """Create a model for processing policy inquiries."""
    config = config or DEFAULT_CONFIG
    
    # Load the optimized model
    json_path = Path(__file__).resolve().parent / "optimized_policies.json"
    
    # Create optimized signature subclass with base instructions as default
    class OptimizedPolicySignature(PolicyAgentSignature):
        """Optimized signature based on PolicyAgentSignature."""
        pass
        
    # Default to the PolicyAgentSignature instructions
    instructions = PolicyAgentSignature.__doc__
    logger.info("Using base instructions from PolicyAgentSignature")
    
    # Load optimized instructions if available
    if os.path.exists(json_path):
        with open(json_path, 'r') as f:
            data = json.load(f)
        
        if "instructions" in data and data["instructions"]:
            instructions = data["instructions"]
            logger.info("Loaded optimized instructions from JSON")
            
            # Ensure date formatting instructions are included
            if f"Dates MUST be in the format {config.date_format}" not in instructions:
                instructions += f"\n    IMPORTANT: Dates MUST be in the format {config.date_format}. For example, use \"2025-03-15\" instead of \"March 15th, 2025\"."
    
    # Set the docstring to the instructions (optimized or base)
    OptimizedPolicySignature.__doc__ = instructions
    
    # Create TracedReAct with signature
    logger.info(f"Creating model: {config.name}_optimized")
    return TracedReAct(
        OptimizedPolicySignature,
        tools=[take_policy_by_number_from_database, query_policy_documentation],
        name=f"{config.name}_optimized",
        tracer=policies_tracer if config.use_tracing else None,
        max_iters=config.max_iterations,
    )


# Create the policies model
policies_model = create_policies_model()


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


def get_prediction_from_model(model, chat_history: str) -> Any:
    """Get prediction from a DSPy model."""
    with policies_tracer.start_as_current_span("get_prediction_from_model") as span:
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
        
        # Validate response
        if hasattr(prediction, "final_response"):
            span.set_attribute("response_length", len(prediction.final_response))
        
        return prediction


@traced_dspy_function(name="policies_dspy")
def policies_optimized_dspy(chat_history: str, config: Optional[ModelConfig] = None) -> PolicyResponseData:
    """Process a policies inquiry using the DSPy model."""
    config = config or DEFAULT_CONFIG
    
    with policies_tracer.start_as_current_span("policies_optimized_dspy") as span:
        span.set_attribute("input_length", len(chat_history))
        start_time = time.perf_counter()
        
        # Initialize language model
        dspy_set_language_model(settings, overwrite_cache_enabled=config.cache_enabled)
        
        # Handle long conversations
        truncation_result = truncate_long_history(chat_history, config)
        chat_history = truncation_result["history"]
        
        # Set tracing attributes for truncation
        if truncation_result["truncated"]:
            span.set_attribute("truncated", True)
            span.set_attribute("original_length", truncation_result["original_length"])
            span.set_attribute("truncated_length", truncation_result["truncated_length"])
        
        # Create response data with defaults
        response_data = PolicyResponseData(truncated=truncation_result["truncated"])
        
        # Generate response
        try:
            # Get prediction from model
            prediction = get_prediction_from_model(policies_model, chat_history)
            
            # Extract final response
            if hasattr(prediction, "final_response") and prediction.final_response:
                response_value = str(prediction.final_response).strip()
                if response_value and response_value != "NoneType":
                    response_data.final_response = response_value
                else:
                    logger.warning("Model returned empty or NoneType response, using default")
            
            # Add optional fields if present
            if hasattr(prediction, "policy_category") and prediction.policy_category:
                response_data.policy_category = prediction.policy_category
                span.set_attribute("has_policy_category", True)
                
            if hasattr(prediction, "policy_number") and prediction.policy_number:
                response_data.policy_number = prediction.policy_number
                span.set_attribute("has_policy_number", True)
                
            if hasattr(prediction, "documentation_reference") and prediction.documentation_reference:
                response_data.documentation_reference = prediction.documentation_reference
                span.set_attribute("has_documentation_reference", True)
                
        except Exception as e:
            logger.error(f"Error generating prediction: {e}", exc_info=True)
            # Default response is already set during initialization
            span.set_attribute("error", str(e))
        
        # Record metrics
        elapsed = time.perf_counter() - start_time
        span.set_attribute("processing_time_ms", elapsed * 1000)
        span.set_attribute("response_length", len(response_data.final_response))
        
        return response_data


if __name__ == "__main__":
    # Test the policies DSPy module
    test_conversation = (
        "User: I need information about my policy.\n"
        "PoliciesAgent: Sure, I can help with that. Could you please provide me with your policy number?\n"
        "User: My policy number is A12345\n"
    )
    
    result = policies_optimized_dspy(test_conversation)
    print(f"Response: {result.final_response}")
    
    if result.policy_category:
        print(f"Policy category: {result.policy_category}")
    
    if result.policy_number:
        print(f"Policy number: {result.policy_number}")
    
    if result.documentation_reference:
        print(f"Documentation reference: {result.documentation_reference}")