"""Input validators for the Policies Agent API."""

from typing import Optional

from fastapi import HTTPException

# Valid policy categories
VALID_CATEGORIES = {"auto", "home", "health", "life"}

# Policy number pattern (letter followed by numbers)
POLICY_NUMBER_PATTERN = r"^[A-Z]\d+$"


def validate_category(category: Optional[str]) -> Optional[str]:
    """Validate policy category.
    
    Args:
        category: Category to validate
        
    Returns:
        Validated category or None
        
    Raises:
        HTTPException: If category is invalid
    """
    if category is None:
        return None
        
    if category.lower() not in VALID_CATEGORIES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid category '{category}'. Valid categories are: {', '.join(sorted(VALID_CATEGORIES))}"
        )
    
    return category.lower()


def validate_query(query: str) -> str:
    """Validate search query.
    
    Args:
        query: Query string to validate
        
    Returns:
        Validated query
        
    Raises:
        HTTPException: If query is invalid
    """
    if not query or not query.strip():
        raise HTTPException(
            status_code=400,
            detail="Query cannot be empty"
        )
    
    if len(query) > 500:
        raise HTTPException(
            status_code=400,
            detail="Query too long (max 500 characters)"
        )
    
    return query.strip()


def validate_policy_number(policy_number: Optional[str]) -> Optional[str]:
    """Validate policy number format.
    
    Args:
        policy_number: Policy number to validate
        
    Returns:
        Validated policy number or None
        
    Raises:
        HTTPException: If policy number format is invalid
    """
    if policy_number is None:
        return None
    
    import re
    
    if not re.match(POLICY_NUMBER_PATTERN, policy_number.upper()):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid policy number format '{policy_number}'. Expected format: letter followed by numbers (e.g., A12345)"
        )
    
    return policy_number.upper()


def validate_document_id(doc_id: str) -> str:
    """Validate document ID.
    
    Args:
        doc_id: Document ID to validate
        
    Returns:
        Validated document ID
        
    Raises:
        HTTPException: If document ID is invalid
    """
    if not doc_id or not doc_id.strip():
        raise HTTPException(
            status_code=400,
            detail="Document ID cannot be empty"
        )
    
    # Basic sanitization to prevent injection
    if any(char in doc_id for char in ['<', '>', '"', "'", '&']):
        raise HTTPException(
            status_code=400,
            detail="Document ID contains invalid characters"
        )
    
    return doc_id.strip()