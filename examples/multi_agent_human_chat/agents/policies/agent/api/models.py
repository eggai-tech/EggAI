"""Pydantic models for the Policies Agent API."""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class PolicyDocument(BaseModel):
    """Policy document model for API responses."""

    id: str
    title: str
    text: str
    category: str
    chunk_index: int
    source_file: str
    relevance: Optional[float] = None

    # Enhanced metadata fields
    page_numbers: List[int] = []
    page_range: Optional[str] = None
    headings: List[str] = []
    citation: Optional[str] = None

    # Relationships
    document_id: Optional[str] = None
    previous_chunk_id: Optional[str] = None
    next_chunk_id: Optional[str] = None
    chunk_position: Optional[float] = None


class SearchResponse(BaseModel):
    """Search response model."""

    query: str
    category: Optional[str]
    total_hits: int
    documents: List[PolicyDocument]


class FullDocumentResponse(BaseModel):
    """Full document response model."""

    document_id: str
    category: str
    source_file: str
    full_text: str
    total_chunks: int
    total_characters: int
    total_tokens: int
    headings: List[str]
    page_numbers: List[int]
    page_range: Optional[str]
    chunk_ids: List[str]
    metadata: Dict[str, Any]


class VectorSearchRequest(BaseModel):
    """Vector search request model."""

    query: str
    category: Optional[str] = None
    max_hits: int = 10
    search_type: str = "hybrid"  # "vector", "hybrid", or "keyword"


class CategoryStats(BaseModel):
    """Category statistics model."""

    name: str
    document_count: int


class ReindexRequest(BaseModel):
    """Reindexing request model."""

    force_rebuild: bool = False
    policy_ids: Optional[List[str]] = None  # If None, reindex all
    
    def validate_policy_ids(self):
        """Validate policy IDs are valid categories."""
        if self.policy_ids:
            valid_ids = {"auto", "home", "health", "life"}
            invalid_ids = [pid for pid in self.policy_ids if pid not in valid_ids]
            if invalid_ids:
                raise ValueError(f"Invalid policy IDs: {invalid_ids}. Valid IDs are: {valid_ids}")
        return self


class ReindexResponse(BaseModel):
    """Reindexing response model."""

    status: str
    workflow_id: str
    total_documents_submitted: int
    policy_ids: List[str]