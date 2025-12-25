from typing import Literal, List, Any
from uuid import UUID

from pydantic import BaseModel

from eggai.schemas import BaseMessage


class ExternalTool(BaseModel):
    """
    Represents an external tool available through MCP (Model Context Protocol).

    This model describes a tool that can be invoked by agents through the MCP adapter.
    Tools are typically external services, APIs, or functions that agents can call
    to perform specific actions or retrieve information.

    Attributes:
        name: Unique identifier for the tool (e.g., "get_weather", "search_web").
        description: Human-readable description of what the tool does.
        parameters: JSON schema defining the tool's input parameters (default: empty dict).
        return_type: JSON schema defining the tool's return value structure (default: empty dict).
    """
    name: str
    description: str
    parameters: dict = {}
    return_type: dict = {}


class ToolListRequest(BaseModel):
    """
    Request to retrieve the list of available tools from an MCP adapter.

    This message is sent when an agent wants to discover what tools are available
    through a particular MCP adapter.

    Attributes:
        call_id: Unique identifier for this request, used to match with the response.
        adapter_name: Name of the MCP adapter to query for available tools.
    """
    call_id: UUID
    adapter_name: str


class ToolListRequestMessage(BaseMessage[ToolListRequest]):
    """Message wrapper for ToolListRequest with a fixed message type."""
    type: Literal["ToolListRequestMessage"] = "ToolListRequestMessage"


class ToolListResponse(BaseModel):
    """
    Response containing the list of available tools from an MCP adapter.

    This message is returned after a ToolListRequest, providing the complete
    list of tools that the agent can invoke through the adapter.

    Attributes:
        call_id: Matches the call_id from the corresponding ToolListRequest.
        tools: List of ExternalTool objects describing available tools.
    """
    call_id: UUID
    tools: List[ExternalTool]


class ToolListResponseMessage(BaseMessage[ToolListResponse]):
    """Message wrapper for ToolListResponse with a fixed message type."""
    type: Literal["ToolListResponseMessage"] = "ToolListResponseMessage"


class ToolCallRequest(BaseModel):
    """
    Request to invoke a specific tool through the MCP adapter.

    This message is sent when an agent wants to execute a tool with specific parameters.

    Attributes:
        call_id: Unique identifier for this request, used to match with the response.
        tool_name: Name of the tool to invoke (must match a tool from ToolListResponse).
        parameters: Dictionary of parameter names and values for the tool (default: empty dict).
    """
    call_id: UUID
    tool_name: str
    parameters: dict = {}


class ToolCallRequestMessage(BaseMessage[ToolCallRequest]):
    """Message wrapper for ToolCallRequest with a fixed message type."""
    type: Literal["ToolCallRequestMessage"] = "ToolCallRequestMessage"


class ToolCallResponse(BaseModel):
    """
    Response from invoking a tool through the MCP adapter.

    This message contains the result of executing a tool, including any data
    returned or error information if the call failed.

    Attributes:
        call_id: Matches the call_id from the corresponding ToolCallRequest.
        tool_name: Name of the tool that was invoked.
        data: The return value from the tool execution (can be any type, default: None).
        is_error: Whether the tool execution failed (True) or succeeded (False).
    """
    call_id: UUID
    tool_name: str
    data: Any = None
    is_error: bool = False


class ToolCallResponseMessage(BaseMessage[ToolCallResponse]):
    """Message wrapper for ToolCallResponse with a fixed message type."""
    type: Literal["ToolCallResponseMessage"] = "ToolCallResponseMessage"
