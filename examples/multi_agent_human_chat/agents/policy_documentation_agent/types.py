"""Type definitions for the Policy Documentation Agent."""

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel


class PolicyCategory(str, Enum):
    """Enumeration of supported policy categories."""
    AUTO = "auto"
    HOME = "home"
    HEALTH = "health"
    LIFE = "life"


class DocumentationRequestType(str, Enum):
    """Types of documentation requests."""
    QUERY = "query"
    SEARCH = "search"
    EXPLAIN = "explain"
    COMPARE = "compare"


class ComponentStatus(str, Enum):
    """Status of RAG components."""
    IDLE = "idle"
    PROCESSING = "processing"
    COMPLETED = "completed"
    ERROR = "error"


class ChatMessage(BaseModel):
    """Represents a chat message in the conversation."""
    role: str
    content: str
    timestamp: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class DocumentMetadata(BaseModel):
    """Metadata for policy documents."""
    category: PolicyCategory
    section: Optional[str] = None
    version: Optional[str] = None
    last_updated: Optional[str] = None


class RetrievedDocument(BaseModel):
    """Represents a document retrieved from the knowledge base."""
    content: str
    score: float
    document_id: str
    document_metadata: DocumentMetadata
    
    
class RetrievalRequest(BaseModel):
    """Request for document retrieval."""
    query: str
    category: Optional[PolicyCategory] = None
    max_documents: int = 5
    threshold: float = 0.5


class RetrievalResponse(BaseModel):
    """Response from document retrieval."""
    documents: List[RetrievedDocument]
    query: str
    total_found: int
    processing_time_ms: Optional[float] = None


class AugmentationRequest(BaseModel):
    """Request for context augmentation."""
    query: str
    documents: List[RetrievedDocument]
    conversation_history: Optional[str] = None
    max_context_length: int = 4000


class AugmentationResponse(BaseModel):
    """Response from context augmentation."""
    augmented_context: str
    document_count: int
    context_length: int


class GenerationRequest(BaseModel):
    """Request for response generation."""
    augmented_context: str
    streaming: bool = False
    temperature: float = 0.1
    max_tokens: int = 2000


class GenerationResponse(BaseModel):
    """Response from generation."""
    response: str
    metadata: Optional[Dict[str, Any]] = None
    processing_time_ms: Optional[float] = None


class ModelConfig(BaseModel):
    """Configuration for the language model."""
    timeout_seconds: float = 30.0
    temperature: float = 0.1
    max_tokens: int = 2000
    truncation_length: int = 8000
    model_name: Optional[str] = None


class AgentMetrics(BaseModel):
    """Metrics for monitoring agent performance."""
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    average_response_time_ms: float = 0.0
    retrieval_cache_hits: int = 0
    retrieval_cache_misses: int = 0


class ComponentHealth(BaseModel):
    """Health status of individual components."""
    component_name: str
    status: ComponentStatus
    last_check: str
    error_message: Optional[str] = None
    metrics: Optional[Dict[str, Any]] = None


class AgentHealth(BaseModel):
    """Overall health status of the agent."""
    agent_name: str
    overall_status: ComponentStatus
    components: List[ComponentHealth]
    uptime_seconds: float
    version: str