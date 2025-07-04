"""Type definitions for the Escalation Agent."""

from typing import Any, Dict, List, Literal, Optional, TypedDict

from pydantic import BaseModel, Field

TicketDepartment = Literal["Technical Support", "Billing", "Sales"]

WorkflowStep = Literal["ask_additional_data", "ask_confirmation", "create_ticket"]

ConfirmationResponse = Literal["yes", "no"]



class ChatMessage(TypedDict, total=False):

    content: str
    role: str


class MessageData(TypedDict, total=False):

    chat_messages: List[ChatMessage]
    connection_id: str
    message_id: str
    session: str


class TicketingRequestMessage(TypedDict):

    id: str
    type: Literal["ticketing_request"]
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


class DspyModelConfig(BaseModel):

    name: str = Field("ticketing_agent", description="Name of the DSPy ticketing model")
    max_iterations: int = Field(
        5, description="Maximum iterations for the model", ge=1, le=10
    )
    use_tracing: bool = Field(True, description="Whether to trace model execution")
    cache_enabled: bool = Field(False, description="Whether to enable model caching")
    timeout_seconds: float = Field(30.0, description="Timeout for model inference in seconds", ge=1.0)



class TicketInfo(BaseModel):

    id: str = Field(..., description="Unique identifier for the ticket")
    policy_number: str = Field(description="Policy number associated with the ticket")
    department: TicketDepartment = Field(..., description="Department for the ticket")
    title: str = Field(..., description="Title of the ticket")
    contact_info: str = Field(..., description="Contact information of the user")
    created_at: str = Field(..., description="Creation timestamp")

    model_config = {"extra": "forbid"}


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
