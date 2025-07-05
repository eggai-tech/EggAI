from enum import Enum
from typing import Literal, Optional, TypedDict

from libraries.types import (
    MessageData,
)
from libraries.types import (
    ModelConfig as BaseModelConfig,
)

WebSocketStateType = Literal["connected", "disconnected", "connecting"]


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


class FrontendModelConfig(BaseModelConfig):
    pass

ModelConfig = FrontendModelConfig


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