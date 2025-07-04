"""Type definitions for the Claims Agent."""

import json
import re
from pathlib import Path
from typing import Any, Callable, Dict, List, Literal, Optional, Tuple, TypedDict

from pydantic import BaseModel, Field, field_validator


class ChatMessage(TypedDict, total=False):

    content: str
    role: str


class MessageData(TypedDict, total=False):

    chat_messages: List[ChatMessage]
    connection_id: str
    message_id: str


class ClaimsRequestMessage(TypedDict):

    id: str
    type: Literal["claim_request"]
    source: str
    data: MessageData
    traceparent: Optional[str]
    tracestate: Optional[str]


class TracedMessageDict(TypedDict, total=False):

    id: str
    type: str
    source: str
    data: Dict[str, Any]
    traceparent: Optional[str]
    tracestate: Optional[str]


ValidatorResult = Tuple[bool, Any]
ValidatorFunction = Callable[[str], ValidatorResult]


class ModelConfig(BaseModel):

    name: str = Field("claims_react", description="Name of the model")
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

    model_config = {"extra": "forbid"}

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

    history: str
    truncated: bool
    original_length: int
    truncated_length: int
