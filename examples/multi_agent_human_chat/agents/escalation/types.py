from typing import Literal, Optional, TypedDict

from pydantic import BaseModel, Field

from libraries.types import (
    ChatMessage as ChatMessage,
)
from libraries.types import (
    MessageData as MessageData,
)
from libraries.types import (
    ModelConfig as BaseModelConfig,
)
from libraries.types import (
    ModelResult as ModelResult,
)
from libraries.types import (
    TracedMessageDict as TracedMessageDict,
)

TicketDepartment = Literal["Technical Support", "Billing", "Sales"]

WorkflowStep = Literal["ask_additional_data", "ask_confirmation", "create_ticket"]

ConfirmationResponse = Literal["yes", "no"]



class TicketingRequestMessage(TypedDict):

    id: str
    type: Literal["ticketing_request"]
    source: str
    data: MessageData
    traceparent: Optional[str]
    tracestate: Optional[str]


class ModelConfig(BaseModelConfig):

    name: str = Field("ticketing_agent", description="Name of the DSPy ticketing model")



class TicketInfo(BaseModel):

    id: str = Field(..., description="Unique identifier for the ticket")
    policy_number: str = Field(description="Policy number associated with the ticket")
    department: TicketDepartment = Field(..., description="Department for the ticket")
    title: str = Field(..., description="Title of the ticket")
    contact_info: str = Field(..., description="Contact information of the user")
    created_at: str = Field(..., description="Creation timestamp")

    model_config = {"extra": "forbid"}


DspyModelConfig = ModelConfig
