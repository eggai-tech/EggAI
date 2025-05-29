import os

from ragatouille import RAGPretrainedModel

from agents.policies.rag.indexing import ensure_index_built
from libraries.logger import get_console_logger
from libraries.tracing import create_tracer

tracer = create_tracer("policies_agent", "rag")
logger = get_console_logger("policies_agent.rag")

_INDEX_LOADED = False
_RAG = None


@tracer.start_as_current_span("retrieve_policies")
def retrieve_policies(query, category=None):
    global _INDEX_LOADED, _RAG

    logger.info(
        f"Retrieving policy information for query: '{query}', category: '{category}'"
    )
    ensure_index_built()

    if not _INDEX_LOADED:
        logger.info("Loading RAG index for the first time")
        index_root = os.path.abspath(
            os.path.join(os.path.dirname(__file__), ".ragatouille")
        )
        index_path = os.path.abspath(
            os.path.join(index_root, "colbert", "indexes", "policies_index")
        )
        logger.debug(f"Using index path: {index_path}")

        try:
            _RAG = RAGPretrainedModel.from_index(index_path)
            _INDEX_LOADED = True
            logger.info("RAG index loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load RAG index: {e}", exc_info=True)
            raise

    try:
        results = _RAG.search(query, index_name="policies_index")
        if category:
            filtered_results = [
                r for r in results if r["document_metadata"]["category"] == category
            ]
            logger.info(
                f"Found {len(filtered_results)} results after filtering by category '{category}'"
            )
            return filtered_results

        logger.info(f"Found {len(results)} results for query")
        return results
    except Exception as e:
        logger.error(f"Error searching RAG index: {e}", exc_info=True)
        return []


if __name__ == "__main__":
    logger.info("Running retrieving module as script")
    res = retrieve_policies("Is Fire Damage Coverage included?")
    logger.info(f"Retrieved {len(res)} results")
    for idx, r in enumerate(res[:3]):
        logger.info(
            f"Result {idx + 1}: {r.get('document_metadata', {}).get('category')} - {r.get('content', '')[:100]}..."
        )
