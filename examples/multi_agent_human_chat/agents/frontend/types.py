"""
Type definitions for the Frontend Agent.

This module contains all type definitions used throughout the frontend agent code,
providing consistent typing and improving code maintainability.
"""
from typing import Any, Dict, List, Literal, Optional, TypedDict

from pydantic import BaseModel, Field

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


class WebSocketConfig(BaseModel):
    """Configuration for websocket connections."""
    ping_interval: float = Field(default=30.0, description="Interval between ping messages in seconds")
    ping_timeout: float = Field(default=10.0, description="Timeout for ping responses in seconds")
    max_message_size: int = Field(default=1024 * 1024, description="Maximum message size in bytes")
    close_timeout: float = Field(default=5.0, description="Timeout for close handshake in seconds")
    
    model_config = {"validate_assignment": True}


class GuardrailsConfig(BaseModel):
    """Configuration for content guardrails."""
    enabled: bool = Field(default=False, description="Whether guardrails are enabled")
    toxic_language_threshold: float = Field(
        default=0.5, 
        description="Threshold for toxic language detection",
        ge=0.0,
        le=1.0
    )
    validation_method: Literal["sentence", "document"] = Field(
        default="sentence", 
        description="Method to use for validation"
    )
    
    model_config = {"validate_assignment": True}


class FrontendConfig(BaseModel):
    """Configuration for the frontend agent."""
    app_name: str = Field(default="frontend_agent", description="Name of the application")
    host: str = Field(default="127.0.0.1", description="Host to bind to")
    port: int = Field(default=8000, description="Port to listen on")
    websocket_path: str = Field(default="/ws", description="Path for websocket connections")
    public_dir: str = Field(default="", description="Directory for static files")
    guardrails: GuardrailsConfig = Field(default_factory=GuardrailsConfig, description="Guardrails configuration")
    websocket: WebSocketConfig = Field(default_factory=WebSocketConfig, description="Websocket configuration")
    
    model_config = {"validate_assignment": True}