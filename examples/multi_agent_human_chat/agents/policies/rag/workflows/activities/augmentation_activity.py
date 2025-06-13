import logging
from typing import Any, Dict, List

from opentelemetry import trace
from temporalio import activity

from shared.utils.opentelemetry import traced

logger = logging.getLogger(__name__)
tracer = trace.get_tracer("policies_agent.rag.activities")


@activity.defn(name="policy_augmentation_activity")
@traced("augmentation_activity")
async def policy_augmentation_activity(retrieval_results: List[Dict[str, Any]], query: str) -> Dict[str, Any]:
    """
    Temporal activity for augmenting retrieved policy information.
    
    Args:
        retrieval_results: Results from the retrieval step
        query: The original user query
        
    Returns:
        Augmented context for generation
    """
    logger.info(f"Starting policy augmentation for query: '{query}' with {len(retrieval_results)} documents")
    
    try:
        # Create augmented context by combining and processing retrieval results
        with tracer.start_as_current_span("create_augmented_context") as span:
            span.set_attribute("query", query)
            span.set_attribute("document_count", len(retrieval_results))
            
            augmented_context = {
                "original_query": query,
                "document_count": len(retrieval_results),
                "combined_content": "",
                "categories": set(),
                "contexts": []
            }
            
            # Extract and combine relevant information
            for i, doc in enumerate(retrieval_results):
                category = doc.get("category", "unknown")
                title = doc.get("title", f"Document {i+1}")
                sections = doc.get("sections", [])
                
                # Add to combined content with proper separation
                if i > 0:
                    augmented_context["combined_content"] += "\n\n---\n\n"
                
                # Add document header
                augmented_context["combined_content"] += f"DOCUMENT: {title} ({category})\n\n"
                
                # Add each relevant section with its reference
                for section in sections:
                    reference = section.get("reference", "")
                    content = section.get("content", "")
                    
                    # Only add content that has both reference and content
                    if reference and content:
                        # Trim section content to reasonable size (max 500 chars per section)
                        section_content = content
                        if len(section_content) > 500:
                            section_content = section_content[:497] + "..."
                        
                        augmented_context["combined_content"] += f"{section_content}\n\n"
                
                augmented_context["categories"].add(category)
                
                # Add structured context
                augmented_context["contexts"].append({
                    "document_index": i,
                    "document_id": doc.get("id", f"doc-{i}"),
                    "category": category,
                    "title": title,
                    "sections": sections,
                    "relevance_score": doc.get("relevance_score", 0)
                })
            
            # Convert set to list for JSON serialization
            augmented_context["categories"] = list(augmented_context["categories"])
            span.set_attribute("categories", str(augmented_context["categories"]))
            
            # If no content was found, provide a helpful message
            if not augmented_context["combined_content"]:
                augmented_context["combined_content"] = "No specific policy information was found for this query. Please try asking a more specific question about your policy coverage."
        
        logger.info(f"Successfully augmented {len(retrieval_results)} policy documents")
        # Return the result directly - let Temporal handle serialization
        return augmented_context
    except Exception as e:
        logger.error(f"Policy augmentation failed: {e}", exc_info=True)
        # Return a minimal context instead of raising an exception
        return {
            "original_query": query,
            "document_count": 0,
            "combined_content": "I'm sorry, but I couldn't find specific information about that in your policy. Could you try asking a more specific question?",
            "categories": [],
            "contexts": []
        }
 