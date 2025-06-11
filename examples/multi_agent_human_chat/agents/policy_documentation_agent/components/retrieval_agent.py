import os
from typing import Any, Dict, List

from eggai import Agent, Channel
from ragatouille import RAGPretrainedModel

from libraries.channels import channels
from libraries.logger import get_console_logger
from libraries.tracing import TracedMessage, create_tracer, traced_handler

retrieval_agent = Agent(name="RetrievalAgent")
logger = get_console_logger("policy_documentation_agent.retrieval")
tracer = create_tracer("policy_documentation_agent", "retrieval")
internal_channel = Channel(channels.internal)

_INDEX_BUILT = False
_INDEX_LOADED = False
_RAG = None


def get_policy_content(policy: str) -> str:
    """Load policy content from markdown files."""
    current_dir = os.path.dirname(__file__)
    policy_path = os.path.abspath(
        os.path.join(current_dir, "..", "policies", policy + ".md")
    )
    with open(policy_path, "r") as f:
        return f.read()


def ensure_index_built() -> None:
    """Ensure the RAG index is built for policy documents."""
    global _INDEX_BUILT
    if _INDEX_BUILT:
        return

    index_root = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", ".ragatouille")
    )
    index_path = os.path.abspath(
        os.path.join(index_root, "colbert", "indexes", "policies_index")
    )

    if not os.path.exists(index_path):
        r = RAGPretrainedModel.from_pretrained(
            "colbert-ir/colbertv2.0", index_root=index_root
        )
        policies_ids = ["health", "auto", "home", "life"]
        document_metadata = [
            {
                "category": policy_id,
                "type": "policy",
            }
            for policy_id in policies_ids
        ]
        my_policies_content = [
            get_policy_content(policy_id) for policy_id in policies_ids
        ]
        r.index(
            index_name="policies_index",
            collection=my_policies_content,
            document_ids=policies_ids,
            document_metadatas=document_metadata,
        )
    else:
        logger.info("Index already built")
    _INDEX_BUILT = True


@tracer.start_as_current_span("retrieve_documents")
def retrieve_documents(query: str, category: str = None) -> List[Dict[str, Any]]:
    """Retrieve relevant documents based on query."""
    global _INDEX_LOADED, _RAG

    logger.info(f"Retrieving documents for query: '{query}', category: '{category}'")
    ensure_index_built()

    if not _INDEX_LOADED:
        logger.info("Loading RAG index for the first time")
        index_root = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", ".ragatouille")
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


@retrieval_agent.subscribe(
    channel=internal_channel,
    filter_by_message=lambda msg: msg.get("type") == "retrieval_request",
    auto_offset_reset="latest",
    group_id="retrieval_agent_group",
)
@traced_handler("handle_retrieval_request")
async def handle_retrieval_request(msg: TracedMessage) -> None:
    """Handle retrieval requests from other components."""
    try:
        query = msg.data.get("query", "")
        category = msg.data.get("category")
        request_id = msg.data.get("request_id", "")

        if not query:
            logger.warning("Empty query in retrieval request")
            await internal_channel.publish(
                TracedMessage(
                    type="retrieval_response",
                    source="RetrievalAgent",
                    data={
                        "request_id": request_id,
                        "documents": [],
                        "error": "Empty query provided",
                    },
                    traceparent=msg.traceparent,
                    tracestate=msg.tracestate,
                )
            )
            return

        logger.info(f"Processing retrieval request: {query}")
        documents = retrieve_documents(query, category)

        await internal_channel.publish(
            TracedMessage(
                type="retrieval_response",
                source="RetrievalAgent",
                data={
                    "request_id": request_id,
                    "documents": documents,
                    "query": query,
                    "category": category,
                },
                traceparent=msg.traceparent,
                tracestate=msg.tracestate,
            )
        )
        logger.info(f"Sent {len(documents)} documents for request {request_id}")

    except Exception as e:
        logger.error(f"Error in retrieval agent: {e}", exc_info=True)
        await internal_channel.publish(
            TracedMessage(
                type="retrieval_response",
                source="RetrievalAgent",
                data={
                    "request_id": msg.data.get("request_id", ""),
                    "documents": [],
                    "error": str(e),
                },
                traceparent=msg.traceparent if "msg" in locals() else None,
                tracestate=msg.tracestate if "msg" in locals() else None,
            )
        )



if __name__ == "__main__":
    logger.info("Running retrieval agent as script")
    results = retrieve_documents("Is Fire Damage Coverage included?")
    logger.info(f"Retrieved {len(results)} results")
    for _idx, r in enumerate(results[:3]):
        logger.info(r)
