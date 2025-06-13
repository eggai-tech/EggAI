"""
Policy document retrieval module.

This module handles retrieving relevant policy documents based on user queries.
It provides a sample implementation that returns documents with relevant section references.
"""

import logging
import re
from typing import Any, Dict, List, Optional

from opentelemetry import trace

from agents.policies.rag.policy_documents import POLICY_DOCUMENTS

logger = logging.getLogger(__name__)
tracer = trace.get_tracer("policies_agent.rag.retrieval")


def extract_section_content(doc_content: str, section: str) -> Optional[Dict[str, str]]:
    """
    Extract content for a specific section from the document.
    
    Args:
        doc_content: The full document content
        section: The section identifier (e.g., "1", "2.1")
        
    Returns:
        Dictionary with 'reference' and 'content' if found, None otherwise
    """
    # Try multiple section patterns
    patterns = [
        f"#### \\*\\*{section}\\. .*\\*\\*",  # Format: #### **1. Title**
        f"### \\*\\*{section}\\. .*\\*\\*",   # Format: ### **1. Title**
        f"## {section}\\. ",                    # Format: ## 1. Title
        f"# .* \\({section}\\)"                 # Original format: # Title (1)
    ]
    
    match = None
    for pattern in patterns:
        match = re.search(pattern, doc_content)
        if match:
            break
    
    if not match:
        return None
        
    section_start = match.start()
    # Find next section - look for any header marker
    section_end = len(doc_content)  # Default to end of document
    for marker in ["####", "###", "##", "#"]:
        next_section = doc_content.find(marker, section_start + 1)
        if next_section != -1 and next_section < section_end:
            section_end = next_section
    
    section_content = doc_content[section_start:section_end].strip()
    return {
        "reference": section,
        "content": section_content
    }

def get_policy_documents_by_category(category: str) -> List[Dict[str, Any]]:
    """
    Get policy documents filtered by category.
    
    Args:
        category: Policy category (auto, home, life, health)
        
    Returns:
        Filtered list of policy documents
    """
    return [doc for doc in POLICY_DOCUMENTS if doc["category"].lower() == category.lower()]

def extract_policy_number_from_query(query: str) -> Optional[str]:
    """
    Extract policy number from a query.
    
    Args:
        query: The user's query
        
    Returns:
        Extracted policy number or None
    """
    # Simple pattern matching for policy numbers
    patterns = [
        r'policy\s+(?:number|#|no\.?)\s+([A-Z0-9-]+)',  # Policy number ABC123
        r'([A-Z]{2,}-\d{5,})',                         # Format like AUTO-12345
        r'([A-Z]{4}-\d{6,})'                           # Format like HOME-123456
    ]
    
    for pattern in patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            return match.group(1)
    
    return None

@tracer.start_as_current_span("retrieve_policies")
def retrieve_policies(query: str, category: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Retrieve relevant policy documents based on the query.
    
    Args:
        query: The user's query
        category: Optional category filter (auto, home, life, health)
        
    Returns:
        List of matching document chunks with relevance scores
    """
    logger.info(f"Retrieving policies for query: '{query}', category: '{category}'")
    
    try:
        # Filter by category if provided
        documents = get_policy_documents_by_category(category) if category else POLICY_DOCUMENTS
        logger.info(f"Found {len(documents)} documents in category '{category}'")
        
        for doc in documents:
            logger.info(f"Document in category '{category}': {doc['id']} - {doc['title']}")
        
        # Extract policy number if present in query
        policy_number = extract_policy_number_from_query(query)
        
        # Convert query to lowercase for matching
        query_lower = query.lower()
        
        # Extract individual words from query (for better matching)
        query_words = set(query_lower.split())
        
        results = []
        
        # Simple keyword-based matching
        for doc in documents:
            # Calculate a simple relevance score based on keyword matches
            content = doc["content"].lower()
            score = 0
            
            # Category match: Give a base score boost for matching the requested category
            if category and doc["category"].lower() == category.lower():
                score += 5
                
            # Check for policy number match
            if policy_number and policy_number in doc["content"]:
                score += 10
            
            # Find direct word matches (not just keywords)
            word_matches = []
            for word in query_words:
                if len(word) > 3 and word in content:  # Only consider words longer than 3 chars
                    score += 1
                    word_matches.append(word)
            
                
            # Count direct query word matches in content
            for word in query_words:
                if len(word) > 3 and word in content:
                    score += 2  # Give higher weight to significant word matches
            
            # If category is specified but no score yet, give a minimum score
            # This ensures we return something in the requested category
            if score == 0 and category and doc["category"].lower() == category.lower():
                score = 1
            
            # Include document if it has any relevance
            if score > 0:
                # Extract relevant sections based on the query
                sections = []
                for section in doc["metadata"]["sections"]:
                    section_data = extract_section_content(doc["content"], section)
                    if section_data:
                        # Check if section is relevant to the query
                        section_content_lower = section_data["content"].lower()
                        relevant = False
                        
                        # Check for direct word matches from query
                        for word in query_words:
                            if len(word) > 3 and word in section_content_lower:
                                relevant = True
                                break
                        
                        if relevant:
                            sections.append(section_data)
                
                # If no sections found but it's the requested category, include the most relevant section
                if not sections and category and doc["category"].lower() == category.lower():
                    # Include the first 1-2 sections as a fallback
                    main_sections = [s for s in doc["metadata"]["sections"] if s.count(".") <= 1][:2]
                    logger.info(f"No relevant sections found, using fallback sections: {main_sections}")
                    
                    for section in main_sections:
                        section_data = extract_section_content(doc["content"], section)
                        if section_data:
                            sections.append(section_data)
                
                # Include document if it has relevant sections
                if sections:
                    # Limit the number of sections to reduce context size
                    # Sort sections by relevance (simple approach: longest sections might be more informative)
                    sections.sort(key=lambda x: len(x["content"]), reverse=True)
                    # Take at most 3 most relevant sections
                    limited_sections = sections[:3]
                    
                    results.append({
                        "id": doc["id"],
                        "category": doc["category"],
                        "title": doc["title"],
                        "sections": limited_sections,
                        "relevance_score": score
                    })
        
        # Sort by relevance score (descending)
        results.sort(key=lambda x: x["relevance_score"], reverse=True)
        
        # Limit to top 2 most relevant documents to further reduce context size
        results = results[:2]
        
        logger.info(f"Retrieved {len(results)} relevant policy documents")
        return results
    
    except Exception as e:
        logger.error(f"Error retrieving policies: {e}", exc_info=True)
        return [] 