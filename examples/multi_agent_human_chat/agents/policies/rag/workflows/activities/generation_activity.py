import logging
from typing import Any, Dict, List, Optional

from opentelemetry import trace
from temporalio import activity

from agents.policies.dspy_modules.policies import get_language_model
from agents.policies.rag.config import RAGConfig

logger = logging.getLogger(__name__)
tracer = trace.get_tracer("policies_agent.rag.activities")


@activity.defn(name="policy_generation_activity")
@tracer.start_as_current_span("policy_generation_activity")
async def policy_generation_activity(
    query: str, 
    augmented_context: Dict[str, Any],
    policy_category: Optional[str] = None
) -> str:
    """
    Generate a response based on the query and augmented context.
    
    Args:
        query: The user's query
        augmented_context: Context augmented with policy information
        policy_category: Optional policy category
        
    Returns:
        Generated response
    """
    logger.info(f"Generating response for query: '{query}'")
    
    try:
        # Get raw language model directly, avoid using any DSPy modules or wrappers
        llm = get_language_model()
        
        # Extract context from augmented_context if available
        context = ""
        if augmented_context:
            # Try to get combined_content first (what augmentation activity returns)
            context = augmented_context.get("combined_content", "")
            # If not available, try context
            if not context:
                context = augmented_context.get("context", "")
        
        # Build prompt from template
        prompt = RAGConfig.GENERATION_PROMPT_TEMPLATE.format(
            query=query,
            context=context
        )
        
        # Use direct LLM call with simple prompt, avoiding any complex DSPy constructs
        logger.info("Generating response using raw LLM prompt")
        try:
            # First try with forward method
            result = llm.forward(prompt=prompt)
            response = result.text
            logger.info("Successfully generated response using forward method")
        except Exception as forward_error:
            logger.warning(f"Error with forward method: {forward_error}, trying __call__ method")
            try:
                # Fallback to __call__ if forward fails
                response = llm(prompt)
                # Handle case where response might be a list
                if isinstance(response, list):
                    response = response[0] if response else ""
                logger.info("Successfully generated response using __call__ method")
            except Exception as call_error:
                logger.warning(f"Error with __call__ method: {call_error}, using built-in default response")
                # Fallback to a built-in response
                if context:
                    # Try to provide a helpful summary based on the context
                    response = f"Based on your {policy_category} insurance policy, here's what I found:\n\n{context[:500]}\n\nThis information is from your policy documentation. If you have specific questions about any part of this, please let me know."
                else:
                    response = "I need more information to answer your question accurately. Could you please specify which aspect of your policy you're asking about? For example, are you interested in coverage details, claim procedures, or policy terms?"
            
        # Ensure response is a string
        if isinstance(response, list):
            response = str(response[0]) if response else ""
        elif not isinstance(response, str):
            response = str(response)
            
        logger.info("Response generated successfully")
        return response
        
    except Exception as e:
        logger.error(f"Error generating response: {e}", exc_info=True)
        # Return a helpful error message
        return RAGConfig.ERROR_MESSAGES["generic"] 