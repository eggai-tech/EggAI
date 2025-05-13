"""
Type definitions for the Policies Agent.

This module contains all type definitions used throughout the policies agent code,
providing consistent typing and improving code maintainability.
"""
from typing import Any, Dict, List, Literal, Optional, TypedDict

from pydantic import BaseModel, Field

# Type alias for policy categories
PolicyCategory = Literal["auto", "life", "home", "health"]


# Forward reference for type hints
PolicyAgentSignature = Any  # Will be imported from dspy_modules


class ChatMessage(TypedDict, total=False):
    """Type definition for a chat message."""
    content: str  # Required message content
    role: str  # Typically "User" or "PoliciesAgent", optional with default "User"


class MessageData(TypedDict, total=False):
    """Type definition for message data in policy requests."""
    chat_messages: List[ChatMessage]  # The conversation history
    connection_id: str  # Unique identifier for the conversation
    message_id: str  # Unique identifier for the message


class PolicyRequestMessage(TypedDict):
    """Type definition for a policy request message."""
    id: str  # Unique message identifier
    type: Literal["policy_request"]  # Message type
    source: str  # Source of the message
    data: MessageData  # Message data with chat history and IDs
    traceparent: Optional[str]  # OpenTelemetry traceparent header
    tracestate: Optional[str]  # OpenTelemetry tracestate header


class TracedMessageDict(TypedDict, total=False):
    """Type definition for traced message dictionary."""
    id: str  # Message ID
    type: str  # Message type
    source: str  # Message source
    data: Dict[str, Any]  # Message data
    traceparent: Optional[str]  # Trace parent
    tracestate: Optional[str]  # Trace state


class TruncationResult(TypedDict):
    """Result of truncating a conversation history."""
    history: str  # Truncated or original history
    truncated: bool  # Whether truncation was performed
    original_length: int  # Original length of the history
    truncated_length: int  # Length after truncation (same as original if not truncated)


class ModelConfig(BaseModel):
    """Configuration for the policies DSPy model."""
    name: str = Field("policies_react", description="Name of the model")
    max_iterations: int = Field(5, description="Maximum iterations for the model", ge=1, le=10)
    use_tracing: bool = Field(True, description="Whether to trace model execution")
    date_format: str = Field("YYYY-MM-DD", description="Required date format for responses")
    cache_enabled: bool = Field(False, description="Whether to enable model caching")
    truncation_length: int = Field(15000, description="Maximum length for conversation history", ge=1000)
    timeout_seconds: float = Field(30.0, description="Timeout for model inference in seconds", ge=1.0)
    

class PolicyResponseData(BaseModel):
    """Result from a policy inquiry."""
    final_response: str = Field(
        "Your next premium payment for policy B67890 is due on 2026-03-15. The amount due is $300.00.", 
        description="Main response to the user"
    )
    policy_category: Optional[PolicyCategory] = Field(None, description="Category of the policy")
    policy_number: Optional[str] = Field(None, description="Policy number if identified")
    documentation_reference: Optional[str] = Field(None, description="Reference to policy documentation")
    truncated: bool = Field(False, description="Whether the input was truncated")
    
    model_config = {"validate_assignment": True}


class ModelResult(BaseModel):
    """Result of a model prediction."""
    response: str = Field(..., description="The generated response text")
    processing_time_ms: float = Field(..., description="Processing time in milliseconds", ge=0)
    success: bool = Field(True, description="Whether the model execution was successful")
    truncated: bool = Field(False, description="Whether the input was truncated")
    original_length: Optional[int] = Field(None, description="Original length of input before truncation")
    truncated_length: Optional[int] = Field(None, description="Length of input after truncation")
    error: Optional[str] = Field(None, description="Error message if execution failed")
    
    model_config = {"validate_assignment": True}


class PolicyRecord(BaseModel):
    """Data structure for a policy record with validation."""
    policy_number: str = Field(..., description="Unique identifier for the policy")
    name: str = Field(..., description="Name of the policyholder")
    premium_amount: float = Field(..., description="Premium amount", gt=0)
    due_date: str = Field(..., description="Due date for payment (YYYY-MM-DD)")
    policy_category: PolicyCategory = Field(..., description="Category of policy")
    start_date: str = Field(..., description="Start date of policy (YYYY-MM-DD)")
    end_date: str = Field(..., description="End date of policy (YYYY-MM-DD)")
    coverage_amount: float = Field(..., description="Total coverage amount", gt=0)
    description: Optional[str] = Field(None, description="Policy description")
    contact_email: Optional[str] = Field(None, description="Contact email address")
    payment_status: Optional[str] = Field(None, description="Current payment status")
    
    model_config = {"extra": "forbid"}  # Prevent extra fields for security


class DocumentationSection(BaseModel):
    """Data structure for a policy documentation section."""
    category: PolicyCategory = Field(..., description="Category of policy")
    section_id: str = Field(..., description="Section identifier (e.g., '3.1')")
    title: str = Field(..., description="Section title")
    content: str = Field(..., description="Section content")