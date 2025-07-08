import json
import re
from pathlib import Path
from typing import Any, Callable, Dict, List, Literal, Optional, Tuple, TypedDict

from pydantic import BaseModel, Field, field_validator

from libraries.communication.protocol import (
    ChatMessage as ChatMessage,
)
from libraries.communication.protocol import (
    MessageData as MessageData,
)
from libraries.core import (
    ModelConfig as BaseModelConfig,
)
from libraries.core import (
    ModelResult as ModelResult,
)


class ClaimsRequestMessage(TypedDict):

    id: str
    type: Literal["claim_request"]
    source: str
    data: MessageData
    traceparent: Optional[str]
    tracestate: Optional[str]



ValidatorResult = Tuple[bool, Any]
ValidatorFunction = Callable[[str], ValidatorResult]


class ModelConfig(BaseModelConfig):
    name: str = Field(default="claims_react", description="Name of the model")


class OptimizationConfig(BaseModel):

    json_path: Path = Field(..., description="Path to optimization JSON file")
    fallback_to_base: bool = Field(
        True, description="Whether to fall back to base model if optimization fails"
    )


class ClaimRecord(BaseModel):

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
