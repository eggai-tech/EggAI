"""
Type definitions for the Frontend Agent.
This module contains all type definitions used throughout the frontend agent code,
providing consistent typing and improving code maintainability.
"""

from typing import Any, Dict, List, Literal, Optional, TypedDict

# Type alias for websocket states
WebSocketStateType = Literal["connected", "disconnected", "connecting"]


class ChatMessage(TypedDict, total=False):
    """Type definition for a chat message."""

    role: str  # "user" or "assistant" or agent name
    content: str  # Required message content
    id: str  # Message ID
    agent: str  # Agent name


class MessageData(TypedDict, total=False):
    """Type definition for message data in websocket interactions."""

    chat_messages: List[ChatMessage]  # The conversation history
    connection_id: str  # Unique identifier for the websocket connection
    message_id: str  # Unique identifier for the message
    message: str  # Message content when sending agent responses
    agent: str  # Agent name when sending responses
    session: str  # Session identifier


class UserMessage(TypedDict):
    """Type definition for a user message from the frontend."""

    id: str  # Unique message identifier
    type: Literal["user_message"]  # Message type
    source: Literal["FrontendAgent"]  # Source of the message
    data: MessageData  # Message data
    traceparent: Optional[str]  # OpenTelemetry traceparent header
    tracestate: Optional[str]  # OpenTelemetry tracestate header


class AgentResponseMessage(TypedDict):
    """Type definition for an agent response message to the frontend."""

    id: str  # Unique message identifier
    type: Literal["agent_message"]  # Message type
    source: str  # Source agent name
    data: MessageData  # Message data
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