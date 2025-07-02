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
    alpha: float = 0.7  # Weight for hybrid search


class CategoryStats(BaseModel):
    """Category statistics model."""

    category: str
    document_count: int


class ReindexRequest(BaseModel):
    """Request model for reindexing operation."""

    clear_existing: bool = True
    categories: Optional[List[str]] = None
    force_rebuild: bool = True


class ReindexResponse(BaseModel):
    """Response model for reindexing operation."""

    status: str
    message: str
    documents_cleared: Optional[int] = None
    documents_queued: int = 0
    errors: List[str] = []
