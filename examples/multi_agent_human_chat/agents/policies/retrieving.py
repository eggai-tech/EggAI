import asyncio
from typing import Any, Dict, List, Optional

from libraries.logger import get_console_logger
from libraries.tracing import create_tracer
from libraries.vespa import VespaClient

tracer = create_tracer("policies_agent", "rag")
logger = get_console_logger("policies_agent")

_VESPA_CLIENT = None


def _get_vespa_client() -> VespaClient:
    """Get or create Vespa client singleton."""
    global _VESPA_CLIENT
    if _VESPA_CLIENT is None:
        _VESPA_CLIENT = VespaClient()
        logger.info("Vespa client initialized")
    return _VESPA_CLIENT


@tracer.start_as_current_span("retrieve_policies")
def retrieve_policies(
    query: str, category: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Retrieve policy information using Vespa search."""
    logger.info(
        f"Retrieving policy information for query: '{query}', category: '{category}'"
    )

    try:
        # Get Vespa client
        vespa_client = _get_vespa_client()
        
        # Run async search in sync context
        try:
            # Try to get the current event loop
            asyncio.get_running_loop()
            # We're in an async context, use thread executor
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(
                    asyncio.run, 
                    vespa_client.search_documents(query, category)
                )
                results = future.result()
        except RuntimeError:
            # No running loop, we're in sync context - use asyncio.run
            results = asyncio.run(vespa_client.search_documents(query, category))
        
        # Convert results to the expected format for compatibility
        formatted_results = []

        logger.info(f"Found {len(results)} results for query.")
        if not results:
            logger.warning("No results found for the query.")
            return []

        for result in results:
            formatted_result = {
                "content": result["text"],
                "document_metadata": {
                    "category": result["category"],
                    "source_file": result["source_file"],
                    "chunk_index": result["chunk_index"],
                },
                "document_id": result["id"],
                "score": result["relevance"]
            }
            formatted_results.append(formatted_result)

        return formatted_results
        
    except Exception as e:
        logger.error(f"Error searching Vespa: {e}", exc_info=True)
        return []


if __name__ == "__main__":
    logger.info("Running retrieving module as script")
    res = retrieve_policies("Is Fire Damage Coverage included?")
    logger.info(f"Retrieved {len(res)} results")
    for idx, r in enumerate(res[:3]):
        logger.info(
            f"Result {idx + 1}: {r.get('document_metadata', {}).get('category')} - {r.get('content', '')[:100]}..."
        )
