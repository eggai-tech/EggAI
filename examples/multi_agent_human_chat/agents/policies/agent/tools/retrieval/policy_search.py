import json
from typing import Any, Dict, List, Optional

from opentelemetry import trace

from agents.policies.agent.services.embeddings import generate_embedding, generate_embedding_async
from agents.policies.agent.utils import run_async_safe
from libraries.integrations.vespa import VespaClient
from libraries.observability.logger import get_console_logger

logger = get_console_logger("policies_agent.tools.retrieval")
tracer = trace.get_tracer("policies_agent_tools_retrieval")

# Global Vespa client instance to reuse connections
_VESPA_CLIENT = None


@tracer.start_as_current_span("search_policy_documentation")
def search_policy_documentation(query: str, category: Optional[str] = None) -> str:
    """
    Search policy documentation and coverage information using RAG.
    Use this for general policy questions that don't require personal policy data.
    Returns a JSON-formatted string with the retrieval results including page citations.

    Args:
        query: The search query string
        category: Optional policy category filter (auto, home, life, health)

    Returns:
        JSON string with search results or error message
    """
    logger.info(
        f"Tool called: search_policy_documentation(query='{query[:50]}...', category='{category}')"
    )
    try:
        # Call retrieve_policies directly - it handles async/sync internally
        results = retrieve_policies(query, category, include_metadata=True)

        if results:
            logger.info(
                f"Found policy information via direct retrieval: {len(results)} results"
            )

            # Enhanced formatting with citations
            formatted_results = []
            for result in results[:2]:  # Top 2 results
                formatted_result = {
                    "content": result["content"],
                    "source": result["document_metadata"]["source_file"],
                    "category": result["document_metadata"]["category"],
                    "relevance_score": result.get("score", 0.0),
                }

                # Add page citation if available
                if "page_info" in result:
                    formatted_result["citation"] = result["page_info"]["citation"]
                    formatted_result["page_numbers"] = result["page_info"][
                        "page_numbers"
                    ]

                # Add section info if available
                if "structure_info" in result and result["structure_info"]["headings"]:
                    formatted_result["section"] = " > ".join(
                        result["structure_info"]["headings"]
                    )

                formatted_results.append(formatted_result)

            return json.dumps(formatted_results, indent=2)

        logger.warning(
            f"No policy information found for query: '{query}', category: '{category}'"
        )
        return "Policy information not found."
    except Exception as e:
        logger.error(f"Error retrieving policy information: {e}", exc_info=True)
        return "Error retrieving policy information."


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


async def _hybrid_search_with_embedding(
    vespa_client: VespaClient, 
    query: str, 
    category: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Perform hybrid search with async embedding generation.
    
    Args:
        vespa_client: Vespa client instance
        query: Search query
        category: Optional category filter
        
    Returns:
        List of search results
    """
    # Generate embedding asynchronously
    query_embedding = await generate_embedding_async(query)
    
    # Perform hybrid search
    results = await vespa_client.hybrid_search(
        query=query,
        query_embedding=query_embedding,
        category=category,
        alpha=0.7  # Default weight for vector search (70% vector, 30% keyword)
    )
    
    return results


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

        # Use hybrid search with async embedding generation
        logger.info("Using hybrid search with embeddings")
        results = run_async_safe(
            _hybrid_search_with_embedding(vespa_client, query, category)
        )

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
