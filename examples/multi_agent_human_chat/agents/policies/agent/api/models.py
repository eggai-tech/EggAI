"""Pydantic models for the Policies Agent API."""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


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
    search_type: Optional[str] = None


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

    query: str = Field(..., min_length=1, max_length=500)
    category: Optional[str] = None
    max_hits: int = Field(10, ge=1, le=100)
    search_type: str = Field("hybrid", pattern="^(vector|hybrid|keyword)$")  # "vector", "hybrid", or "keyword"
    
    @field_validator('query')
    @classmethod
    def validate_query_length(cls, v):
        if len(v) > 500:
            raise ValueError("Query too long. Maximum 500 characters allowed.")
        if not v.strip():
            raise ValueError("Query cannot be empty.")
        return v


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