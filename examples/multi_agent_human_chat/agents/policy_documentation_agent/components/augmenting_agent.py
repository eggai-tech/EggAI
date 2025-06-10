from typing import Any, Dict, List

from eggai import Agent, Channel

from libraries.channels import channels
from libraries.logger import get_console_logger
from libraries.tracing import TracedMessage, create_tracer, traced_handler

augmenting_agent = Agent(name="AugmentingAgent")
logger = get_console_logger("policy_documentation_agent.augmenting")
tracer = create_tracer("policy_documentation_agent", "augmenting")
internal_channel = Channel(channels.internal)


@tracer.start_as_current_span("augment_context")
def augment_context(
    query: str, documents: List[Dict[str, Any]], max_context_length: int = 4000
) -> str:
    """Augment the query with retrieved document context."""
    if not documents:
        logger.warning("No documents provided for context augmentation")
        return f"Query: {query}\n\nNo relevant policy documents found."

    # Sort documents by relevance score if available
    sorted_docs = sorted(documents, key=lambda x: x.get("score", 0), reverse=True)

    context_parts = [f"Query: {query}", "Relevant Policy Information:"]
    current_length = len("\n".join(context_parts))

    for i, doc in enumerate(sorted_docs):
        content = doc.get("content", "")
        metadata = doc.get("document_metadata", {})
        category = metadata.get("category", "unknown")

        doc_section = f"\n--- Policy {category.upper()} (Relevance: {doc.get('score', 0):.3f}) ---\n{content}"

        if current_length + len(doc_section) > max_context_length:
            if i == 0:
                # If even the first document is too long, truncate it
                available_space = max_context_length - current_length - 100
                truncated_content = content[:available_space] + "..."
                doc_section = f"\n--- Policy {category.upper()} (Relevance: {doc.get('score', 0):.3f}) ---\n{truncated_content}"
                context_parts.append(doc_section)
            break

        context_parts.append(doc_section)
        current_length += len(doc_section)

    augmented_context = "\n".join(context_parts)
    logger.info(
        f"Augmented context with {len([p for p in context_parts if p.startswith('---')])} documents, total length: {len(augmented_context)}"
    )

    return augmented_context


@tracer.start_as_current_span("format_context_for_generation")
def format_context_for_generation(
    conversation_history: str, augmented_context: str
) -> str:
    """Format the augmented context with conversation history for generation."""
    formatted_context = f"""Based on the following policy information, please provide a helpful and accurate response to the user's query.

{augmented_context}

Conversation History:
{conversation_history}

Instructions:
- Use only the information provided in the policy documents above
- If the information is not available in the provided policies, clearly state this
- Be specific and cite which policy section your answer comes from when possible
- Maintain a helpful and professional tone
"""

    logger.info(
        f"Formatted context for generation, total length: {len(formatted_context)}"
    )
    return formatted_context


@augmenting_agent.subscribe(
    channel=internal_channel,
    filter_by_message=lambda msg: msg.get("type") == "augmentation_request",
    auto_offset_reset="latest",
    group_id="augmenting_agent_group",
)
@traced_handler("handle_augmentation_request")
async def handle_augmentation_request(msg: TracedMessage) -> None:
    """Handle augmentation requests from other components."""
    try:
        query = msg.data.get("query", "")
        documents = msg.data.get("documents", [])
        conversation_history = msg.data.get("conversation_history", "")
        request_id = msg.data.get("request_id", "")
        max_context_length = msg.data.get("max_context_length", 4000)

        if not query:
            logger.warning("Empty query in augmentation request")
            await internal_channel.publish(
                TracedMessage(
                    type="augmentation_response",
                    source="AugmentingAgent",
                    data={
                        "request_id": request_id,
                        "augmented_context": "",
                        "error": "Empty query provided",
                    },
                    traceparent=msg.traceparent,
                    tracestate=msg.tracestate,
                )
            )
            return

        logger.info(
            f"Processing augmentation request: {query} with {len(documents)} documents"
        )

        # Augment the context with retrieved documents
        augmented_context = augment_context(query, documents, max_context_length)

        # Format for generation if conversation history is provided
        if conversation_history:
            formatted_context = format_context_for_generation(
                conversation_history, augmented_context
            )
        else:
            formatted_context = augmented_context

        await internal_channel.publish(
            TracedMessage(
                type="augmentation_response",
                source="AugmentingAgent",
                data={
                    "request_id": request_id,
                    "augmented_context": formatted_context,
                    "query": query,
                    "document_count": len(documents),
                },
                traceparent=msg.traceparent,
                tracestate=msg.tracestate,
            )
        )
        logger.info(f"Sent augmented context for request {request_id}")

    except Exception as e:
        logger.error(f"Error in augmenting agent: {e}", exc_info=True)
        await internal_channel.publish(
            TracedMessage(
                type="augmentation_response",
                source="AugmentingAgent",
                data={
                    "request_id": msg.data.get("request_id", ""),
                    "augmented_context": "",
                    "error": str(e),
                },
                traceparent=msg.traceparent if "msg" in locals() else None,
                tracestate=msg.tracestate if "msg" in locals() else None,
            )
        )


if __name__ == "__main__":
    logger.info("Running augmenting agent as script")

    # Test data
    test_documents = [
        {
            "content": "Fire damage is covered under comprehensive insurance with a $500 deductible.",
            "document_metadata": {"category": "auto"},
            "score": 0.95,
        },
        {
            "content": "Home insurance covers fire damage with full replacement cost coverage.",
            "document_metadata": {"category": "home"},
            "score": 0.87,
        },
    ]

    result = augment_context("Is fire damage covered?", test_documents)
    logger.info(f"Augmented result: {result[:200]}...")
