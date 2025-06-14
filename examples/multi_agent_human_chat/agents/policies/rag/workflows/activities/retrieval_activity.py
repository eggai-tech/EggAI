import logging
from typing import Any, Dict, List, Optional

from opentelemetry import trace
from temporalio import activity

from agents.policies.rag.retrieving import retrieve_policies

logger = logging.getLogger(__name__)
tracer = trace.get_tracer("policies_agent.rag.activities")

@activity.defn(name="retrieve_policy_documents")
@tracer.start_as_current_span("retrieve_policy_documents")
async def retrieve_policy_documents(query: str, category: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Retrieve relevant policy documents based on the query.
    
    Args:
        query: The user's query
        category: Optional policy category (auto, home, life, health)
        
    Returns:
        List of relevant policy documents with metadata
    """
    logger.info(f"Retrieving policy documents for query: '{query}', category: '{category}'")
    
    try:
        # Call the sync retrieval function
        results = retrieve_policies(query, category)
        
        logger.info(f"Retrieved {len(results)} relevant policy documents")
        # Return the results directly - Pydantic converter will handle serialization
        return results
    
    except Exception as e:
        logger.error(f"Error retrieving policy documents: {e}", exc_info=True)
        return []