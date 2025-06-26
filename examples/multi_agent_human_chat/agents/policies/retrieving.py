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


def format_citation(result: Dict[str, Any]) -> str:
    """Format a citation with page numbers."""
    source_file = result.get("source_file", "Unknown")
    page_range = result.get("page_range", "")

    if page_range:
        return f"{source_file}, page {page_range}"
    return source_file


@tracer.start_as_current_span("retrieve_policies")
def retrieve_policies(
    query: str, category: Optional[str] = None, include_metadata: bool = True
) -> List[Dict[str, Any]]:
    """Retrieve policy information using Vespa search with enhanced metadata.

    Args:
        query: Search query string
        category: Optional category filter
        include_metadata: Whether to include enhanced metadata in results

    Returns:
        List of search results with enhanced metadata
    """
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
                    asyncio.run, vespa_client.search_documents(query, category)
                )
                results = future.result()
        except RuntimeError:
            # No running loop, we're in sync context - use asyncio.run
            results = asyncio.run(vespa_client.search_documents(query, category))

        # Convert results to the expected format with enhanced metadata
        formatted_results = []

        logger.info(f"Found {len(results)} results for query.")
        if not results:
            logger.warning("No results found for the query.")
            return []

        for result in results:
            # Base result structure
            formatted_result = {
                "content": result["text"],
                "document_metadata": {
                    "category": result["category"],
                    "source_file": result["source_file"],
                    "chunk_index": result["chunk_index"],
                },
                "document_id": result["id"],
                "score": result.get("relevance", 0.0),
            }

            # Add enhanced metadata if requested
            if include_metadata:
                # Page information
                formatted_result["page_info"] = {
                    "page_numbers": result.get("page_numbers", []),
                    "page_range": result.get("page_range", ""),
                    "citation": format_citation(result),
                }

                # Document structure
                formatted_result["structure_info"] = {
                    "headings": result.get("headings", []),
                    "section_path": result.get("section_path", []),
                    "chunk_position": result.get("chunk_position", 0.0),
                }

                # Relationships
                formatted_result["relationships"] = {
                    "document_id": result.get("document_id", ""),
                    "previous_chunk_id": result.get("previous_chunk_id"),
                    "next_chunk_id": result.get("next_chunk_id"),
                }

                # Metrics
                formatted_result["metrics"] = {
                    "char_count": result.get("char_count", 0),
                    "token_count": result.get("token_count", 0),
                }

                # Add to main document metadata for backward compatibility
                formatted_result["document_metadata"].update(
                    {
                        "page_numbers": result.get("page_numbers", []),
                        "page_range": result.get("page_range", ""),
                        "headings": result.get("headings", []),
                    }
                )

            formatted_results.append(formatted_result)

        # Log sample metadata for verification
        if formatted_results and include_metadata:
            sample = formatted_results[0]
            logger.info(
                f"Sample result metadata - Pages: {sample['page_info']['page_range']}, "
                f"Headings: {sample['structure_info']['headings'][:2] if sample['structure_info']['headings'] else 'None'}"
            )

        return formatted_results

    except Exception as e:
        logger.error(f"Error searching Vespa: {e}", exc_info=True)
        return []


def retrieve_policy_with_context(
    query: str, category: Optional[str] = None, include_neighbors: bool = False
) -> List[Dict[str, Any]]:
    """Retrieve policy information with additional context from neighboring chunks.

    Args:
        query: Search query string
        category: Optional category filter
        include_neighbors: Whether to fetch previous/next chunks for context

    Returns:
        List of search results with enhanced metadata and optional context
    """
    results = retrieve_policies(query, category, include_metadata=True)

    if not include_neighbors or not results:
        return results

    # Enhance results with neighboring chunks for better context
    vespa_client = _get_vespa_client()
    enhanced_results = []

    for result in results[:5]:  # Limit to top 5 to avoid too many queries
        enhanced_result = result.copy()

        # Try to fetch neighboring chunks
        relationships = result.get("relationships", {})
        context_chunks = []

        # Fetch previous chunk if available
        if relationships.get("previous_chunk_id"):
            try:
                prev_results = asyncio.run(
                    vespa_client.search_documents(
                        f'id:"{relationships["previous_chunk_id"]}"', max_hits=1
                    )
                )
                if prev_results:
                    context_chunks.append(
                        {
                            "type": "previous",
                            "content": prev_results[0]["text"][:200] + "...",
                        }
                    )
            except Exception as e:
                logger.warning(f"Failed to fetch previous chunk: {e}")

        # Fetch next chunk if available
        if relationships.get("next_chunk_id"):
            try:
                next_results = asyncio.run(
                    vespa_client.search_documents(
                        f'id:"{relationships["next_chunk_id"]}"', max_hits=1
                    )
                )
                if next_results:
                    context_chunks.append(
                        {
                            "type": "next",
                            "content": "..." + next_results[0]["text"][:200],
                        }
                    )
            except Exception as e:
                logger.warning(f"Failed to fetch next chunk: {e}")

        if context_chunks:
            enhanced_result["context_chunks"] = context_chunks

        enhanced_results.append(enhanced_result)

    return enhanced_results


if __name__ == "__main__":
    logger.info("Running retrieving module as script")
    res = retrieve_policies("Is Fire Damage Coverage included?")
    logger.info(f"Retrieved {len(res)} results")
    for idx, r in enumerate(res[:3]):
        logger.info(
            f"Result {idx + 1}: {r.get('document_metadata', {}).get('category')} - "
            f"Pages: {r.get('page_info', {}).get('page_range', 'N/A')} - "
            f"{r.get('content', '')[:100]}..."
        )
