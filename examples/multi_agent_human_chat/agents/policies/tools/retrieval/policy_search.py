"""Policy documentation search tool."""

import json
import threading
from typing import Optional

from opentelemetry import trace

from libraries.logger import get_console_logger

logger = get_console_logger("policies_agent.tools.retrieval")
tracer = trace.get_tracer("policies_agent_tools_retrieval")


class ThreadWithResult(threading.Thread):
    """Thread that returns a result."""

    def __init__(self, target, args=(), kwargs=None):
        super().__init__(target=target, args=args, kwargs=kwargs or {})
        self._result = None

    def run(self):
        if self._target:
            self._result = self._target(*self._args, **self._kwargs)

    def join(self, *args):
        super().join(*args)
        return self._result


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
        from agents.policies.retrieving import retrieve_policies

        thread = ThreadWithResult(
            target=retrieve_policies,
            args=(query, category, True),  # Include metadata
        )
        thread.start()
        results = thread.join()

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
