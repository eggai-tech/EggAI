"""Type definitions for the Escalation Agent.

This module contains all type definitions used throughout the escalation agent code,
providing consistent typing and improving code maintainability.
"""

from typing import Any, Dict, List, Literal, Optional, TypedDict

from pydantic import BaseModel, Field

# Type alias for ticket departments
TicketDepartment = Literal["Technical Support", "Billing", "Sales"]

# Type alias for workflow steps
WorkflowStep = Literal["ask_additional_data", "ask_confirmation", "create_ticket"]

# Type alias for confirmation responses
ConfirmationResponse = Literal["yes", "no"]

# Forward reference for type hints
TicketingAgentSignature = Any  # Will be imported from dspy modules when created


class ChatMessage(TypedDict, total=False):
    """Type definition for a chat message."""

    content: str  # Required message content
    role: str  # Typically "User" or "TicketingAgent", optional with default "User"


class MessageData(TypedDict, total=False):
    """Type definition for message data in ticketing requests."""

    chat_messages: List[ChatMessage]  # The conversation history
    connection_id: str  # Unique identifier for the conversation
    message_id: str  # Unique identifier for the message
    session: str  # Session identifier for the conversation


class TicketingRequestMessage(TypedDict):
    """Type definition for a ticketing request message."""

    id: str  # Unique message identifier
    type: Literal["ticketing_request"]  # Message type
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


class DspyModelConfig(BaseModel):
    """Configuration for the ticketing DSPy model."""

    name: str = Field(
        "ticketing_agent", description="Name of the DSPy ticketing model"
    )
    max_iterations: int = Field(
        5, description="Maximum iterations for the model", ge=1, le=10
    )
    use_tracing: bool = Field(
        True, description="Whether to trace model execution"
    )
    cache_enabled: bool = Field(
        False, description="Whether to enable model caching"
    )
    timeout_seconds: float = Field(
        30.0,
        description="Timeout for model inference in seconds",
        ge=1.0,
    )


# SessionData no longer needed with simplified intelligent agent approach


class TicketInfo(BaseModel):
    """Data structure for ticket information with validation."""

    id: str = Field(..., description="Unique identifier for the ticket")
    policy_number: str = Field(description="Policy number associated with the ticket")
    department: TicketDepartment = Field(..., description="Department for the ticket")
    title: str = Field(..., description="Title of the ticket")
    contact_info: str = Field(..., description="Contact information of the user")
    created_at: str = Field(..., description="Creation timestamp")

    model_config = {"extra": "forbid"}  # Prevent extra fields for security


class ModelResult(BaseModel):
    """Result of a model prediction."""

    message: str = Field(..., description="The generated message to the user")
    processing_time_ms: float = Field(
        ..., description="Processing time in milliseconds", ge=0
    )
    success: bool = Field(
        True, description="Whether the model execution was successful"
    )
    error: Optional[str] = Field(None, description="Error message if execution failed")

    model_config = {"validate_assignment": True}
