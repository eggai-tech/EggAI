"""
Type definitions for the Claims Agent.

This module contains all type definitions used throughout the claims agent code,
providing consistent typing and improving code maintainability.
"""

import json
import re
from pathlib import Path
from typing import Any, Callable, Dict, List, Literal, Optional, Tuple, TypedDict

from pydantic import BaseModel, Field, field_validator


class ChatMessage(TypedDict, total=False):
    """Type definition for a chat message."""

    content: str  # Required message content
    role: str  # Typically "User" or "ClaimsAgent", optional with default "User"


class MessageData(TypedDict, total=False):
    """Type definition for message data in claims requests."""

    chat_messages: List[ChatMessage]  # The conversation history
    connection_id: str  # Unique identifier for the conversation
    message_id: str  # Unique identifier for the message


class ClaimsRequestMessage(TypedDict):
    """Type definition for a claims request message."""

    id: str  # Unique message identifier
    type: Literal["claim_request"]  # Message type
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


# Type for field validation functions
ValidatorResult = Tuple[bool, Any]
ValidatorFunction = Callable[[str], ValidatorResult]


class ModelConfig(BaseModel):
    """Configuration for the claims DSPy model."""

    name: str = Field(..., description="Name of the model")
    max_iterations: int = Field(
        5, description="Maximum iterations for the model", ge=1, le=10
    )
    use_tracing: bool = Field(True, description="Whether to trace model execution")
    cache_enabled: bool = Field(False, description="Whether to enable model caching")
    truncation_length: int = Field(
        15000, description="Maximum length for conversation history", ge=1000
    )
    timeout_seconds: float = Field(
        30.0, description="Timeout for model inference in seconds", ge=1.0
    )


class ModelResult(BaseModel):
    """Result of a model prediction."""

    response: str = Field(..., description="The generated response text")
    processing_time_ms: float = Field(
        ..., description="Processing time in milliseconds", ge=0
    )
    success: bool = Field(
        True, description="Whether the model execution was successful"
    )
    truncated: bool = Field(False, description="Whether the input was truncated")
    original_length: Optional[int] = Field(
        None, description="Original length of input before truncation"
    )
    truncated_length: Optional[int] = Field(
        None, description="Length of input after truncation"
    )
    error: Optional[str] = Field(None, description="Error message if execution failed")

    model_config = {"validate_assignment": True}


class OptimizationConfig(BaseModel):
    """Configuration for model optimization loading."""

    json_path: Path = Field(..., description="Path to optimization JSON file")
    fallback_to_base: bool = Field(
        True, description="Whether to fall back to base model if optimization fails"
    )


class ClaimRecord(BaseModel):
    """Data structure for an insurance claim record with validation."""

    claim_number: str = Field(..., description="Unique identifier for the claim")
    policy_number: str = Field(
        ..., description="Policy number associated with the claim"
    )
    status: str = Field(..., description="Current status of the claim")
    next_steps: str = Field(..., description="Next steps required for claim processing")
    outstanding_items: List[str] = Field(
        default_factory=list, description="Items pending for claim processing"
    )
    estimate: Optional[float] = Field(None, description="Estimated payout amount", gt=0)
    estimate_date: Optional[str] = Field(
        None, description="Estimated date for payout (YYYY-MM-DD)"
    )
    details: Optional[str] = Field(
        None, description="Detailed description of the claim"
    )
    address: Optional[str] = Field(None, description="Address related to the claim")
    phone: Optional[str] = Field(None, description="Contact phone number")
    damage_description: Optional[str] = Field(
        None, description="Description of damage or loss"
    )
    contact_email: Optional[str] = Field(None, description="Contact email address")

    model_config = {"extra": "forbid"}  # Prevent extra fields for security

    @field_validator("estimate_date")
    @classmethod
    def validate_date_format(cls, v):
        if v is None:
            return v
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", v):
            raise ValueError("Date must be in YYYY-MM-DD format")
        return v

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v):
        if v is None:
            return v
        if not re.match(r"^\+?[\d\-\(\) ]{7,}$", v):
            raise ValueError("Invalid phone number format")
        return v

    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in self.model_dump().items() if v is not None}

    def to_json(self) -> str:
        return json.dumps(self.to_dict())


class TruncationResult(TypedDict):
    """Result of truncating a conversation history."""

    history: str  # Truncated or original history
    truncated: bool  # Whether truncation was performed
    original_length: int  # Original length of the history
    truncated_length: int  # Length after truncation (same as original if not truncated)
