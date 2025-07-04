"""Type definitions for the Frontend Agent."""

from typing import Any, Dict, List, Literal, Optional, TypedDict

WebSocketStateType = Literal["connected", "disconnected", "connecting"]


class ChatMessage(TypedDict, total=False):

    role: str
    content: str
    id: str
    agent: str


class MessageData(TypedDict, total=False):

    chat_messages: List[ChatMessage]
    connection_id: str
    message_id: str
    message: str
    agent: str
    session: str


class UserMessage(TypedDict):

    id: str
    type: Literal["user_message"]
    source: Literal["FrontendAgent"]
    data: MessageData
    traceparent: Optional[str]
    tracestate: Optional[str]


class AgentResponseMessage(TypedDict):

    id: str
    type: Literal["agent_message"]
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


from enum import Enum


class MessageType(str, Enum):
    USER_MESSAGE = "user_message"
    AGENT_MESSAGE = "agent_message"
    AGENT_MESSAGE_STREAM_START = "agent_message_stream_start"
    AGENT_MESSAGE_STREAM_WAITING_MESSAGE = "agent_message_stream_waiting_message"
    AGENT_MESSAGE_STREAM_CHUNK = "agent_message_stream_chunk"
    AGENT_MESSAGE_STREAM_END = "agent_message_stream_end"
    ASSISTANT_MESSAGE = "assistant_message"
    ASSISTANT_MESSAGE_STREAM_START = "assistant_message_stream_start"
    ASSISTANT_MESSAGE_STREAM_WAITING_MESSAGE = "assistant_message_stream_waiting_message"
    ASSISTANT_MESSAGE_STREAM_CHUNK = "assistant_message_stream_chunk"
    ASSISTANT_MESSAGE_STREAM_END = "assistant_message_stream_end"