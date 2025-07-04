"""
Type definitions for the Billing Agent.

This module contains all type definitions used throughout the billing agent code,
providing consistent typing and improving code maintainability.
"""

from typing import Optional, TypedDict

from pydantic import BaseModel, Field

# Message type constants
MESSAGE_TYPE_BILLING_REQUEST: str = "billing_request"


class ChatMessage(TypedDict, total=False):
    """Type definition for a chat message."""

    content: str  # Required message content
    role: str  # Typically "User" or "BillingAgent", optional with default "User"




class ModelConfig(BaseModel):
    """Configuration for the billing DSPy model."""

    name: str = Field("billing_react", description="Name of the model")
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


class BillingRecord(BaseModel):
    """Data structure for a billing record with validation."""

    policy_number: str = Field(..., description="Unique identifier for the policy")
    customer_name: str = Field(..., description="Name of the customer")
    amount_due: float = Field(..., description="Amount due", ge=0)
    due_date: str = Field(..., description="Due date for payment (YYYY-MM-DD)")
    billing_status: str = Field(..., description="Current billing status")
    billing_cycle: str = Field(
        ..., description="Billing cycle (monthly, quarterly, etc.)"
    )
    last_payment_date: Optional[str] = Field(
        None, description="Date of last payment (YYYY-MM-DD)"
    )
    last_payment_amount: Optional[float] = Field(
        None, description="Amount of last payment", ge=0
    )
    next_payment_amount: Optional[float] = Field(
        None, description="Amount of next payment", ge=0
    )
    contact_email: Optional[str] = Field(None, description="Contact email address")
    contact_phone: Optional[str] = Field(None, description="Contact phone number")

    model_config = {"extra": "forbid"}  # Prevent extra fields for security

__all__ = [
    "ChatMessage",
    "ModelConfig",
    "ModelResult",
    "BillingRecord",
    "MESSAGE_TYPE_BILLING_REQUEST",
]


