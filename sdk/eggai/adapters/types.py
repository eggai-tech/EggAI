from typing import Literal, List, Any
from uuid import UUID

from pydantic import BaseModel

from eggai.schemas import BaseMessage


class ExternalTool(BaseModel):
    name: str
    description: str
    parameters: dict = {}
    return_type: dict = {}


class ToolListRequest(BaseModel):
    call_id: UUID
    adapter_name: str


class ToolListRequestMessage(BaseMessage[ToolListRequest]):
    type: Literal["ToolListRequestMessage"] = "ToolListRequestMessage"


class ToolListResponse(BaseModel):
    call_id: UUID
    tools: List[ExternalTool]


class ToolListResponseMessage(BaseMessage[ToolListResponse]):
    type: Literal["ToolListResponseMessage"] = "ToolListResponseMessage"


class ToolCallRequest(BaseModel):
    call_id: UUID
    tool_name: str
    parameters: dict = {}


class ToolCallRequestMessage(BaseMessage[ToolCallRequest]):
    type: Literal["ToolCallRequestMessage"] = "ToolCallRequestMessage"


class ToolCallResponse(BaseModel):
    call_id: UUID
    tool_name: str
    data: Any = None
    is_error: bool = False


class ToolCallResponseMessage(BaseMessage[ToolCallResponse]):
    type: Literal["ToolCallResponseMessage"] = "ToolCallResponseMessage"
