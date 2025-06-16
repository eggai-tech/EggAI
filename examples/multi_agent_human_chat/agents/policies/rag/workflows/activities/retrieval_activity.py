from temporalio import activity

from agents.policies.rag.retrieving import retrieve_policies
from libraries.logger import get_console_logger

logger = get_console_logger("policies_agent.rag.temporal")


@activity.defn
async def policy_retrieval_activity(query: str, category: str = None) -> list:
    """
    Temporal activity for retrieving policy information.

    Args:
        query: The search query
        category: Optional category filter

    Returns:
        List of retrieved policy documents
    """
    logger.info(
        f"Starting policy retrieval for query: '{query}', category: '{category}'"
    )

    try:
        results = retrieve_policies(query, category)
        logger.info(f"Successfully retrieved {len(results)} policy documents")
        return results
    except Exception as e:
        logger.error(f"Policy retrieval failed: {e}", exc_info=True)
        raise e
