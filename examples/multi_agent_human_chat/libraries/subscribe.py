"""
Type-safe wrappers and utilities for EggAI subscribe decorators.

This module provides better typing for subscribe decorators without modifying the SDK.

Message Flow Overview:
======================

Frontend Agent:
  Receives: user input via WebSocket
  Publishes: UserMessage → human channel
  
Triage Agent:
  Subscribes to: UserMessage (human channel)
  Publishes: BillingRequestMessage | ClaimRequestMessage | PolicyRequestMessage | EscalationRequestMessage → agents channel
  
Billing/Claims/Policies/Escalation Agents:
  Subscribe to: *RequestMessage (agents channel)
  Publish: AgentMessage, StreamChunkMessage, StreamEndMessage → human/human_stream channels
  
Audit Agent:
  Subscribes to: all messages (agents + human channels)
  Publishes: AuditLogMessage → audit_logs channel

Message Payload Examples:
========================

UserMessage:
{
  "id": "uuid",
  "type": MessageType.USER_MESSAGE,  // "user_message"
  "source": AgentName.FRONTEND,       // "Frontend"
  "data": {
    "connection_id": "websocket-123",
    "chat_messages": [
      {"role": "user", "content": "What's my premium?"}
    ]
  }
}

BillingRequestMessage:
{
  "id": "uuid", 
  "type": MessageType.BILLING_REQUEST, // "billing_request"
  "source": AgentName.TRIAGE,          // "Triage"
  "data": {
    "connection_id": "websocket-123",
    "chat_messages": [
      {"role": "user", "content": "What's my premium?"},
      {"role": "assistant", "content": "I'll help you check your premium."}
    ]
  }
}

AgentMessage:
{
  "id": "uuid",
  "type": MessageType.AGENT_MESSAGE,  // "agent_message"
  "source": AgentName.BILLING,        // "Billing"
  "data": {
    "connection_id": "websocket-123",
    "message": "Your current premium is $150/month.",
    "agent": "Billing"
  }
}
"""

from enum import Enum
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Literal,
    Optional,
    Protocol,
    TypedDict,
    TypeGuard,
    TypeVar,
    Union,
)

from eggai import Agent, Channel
from faststream.kafka import KafkaMessage

from libraries.tracing import TracedMessage


# Message type constants
class MessageType(str, Enum):
    """Standard message types in the system."""
    # User messages
    USER_MESSAGE = "user_message"
    
    # Agent requests (from Triage)
    BILLING_REQUEST = "billing_request"
    CLAIM_REQUEST = "claim_request"
    POLICY_REQUEST = "policy_request"
    ESCALATION_REQUEST = "escalation_request"
    
    # Agent responses
    AGENT_MESSAGE = "agent_message"
    AGENT_MESSAGE_STREAM_START = "agent_message_stream_start"
    AGENT_MESSAGE_STREAM_CHUNK = "agent_message_stream_chunk"
    AGENT_MESSAGE_STREAM_END = "agent_message_stream_end"
    
    # System messages
    AUDIT_LOG = "audit_log"
    ERROR = "error"
    
    
class AgentName(str, Enum):
    """Standard agent names in the system."""
    FRONTEND = "Frontend"
    TRIAGE = "Triage"
    BILLING = "Billing"
    CLAIMS = "Claims"
    POLICIES = "Policies"
    ESCALATION = "Escalation"
    AUDIT = "Audit"
    AUDIT_AGENT = "AuditAgent"  # Alternative name
    
    
class AuditCategory(str, Enum):
    """Audit event categories."""
    SYSTEM_OPERATIONS = "System Operations"
    USER_COMMUNICATION = "User Communication"
    AGENT_PROCESSING = "Agent Processing"
    ERROR = "Error"
    OTHER = "Other"


class OffsetReset(str, Enum):
    """Kafka consumer offset reset options."""
    LATEST = "latest"      # Start reading at the latest record
    EARLIEST = "earliest"  # Start reading at the earliest record  
    NONE = "none"         # Throw exception if no previous offset is found


# Base message data payloads
class MessageData(TypedDict):
    """Base message data payload."""
    connection_id: str
    

class ChatMessage(TypedDict):
    """Individual chat message structure."""
    role: Literal["user", "assistant", "system"]
    content: str
    agent: Optional[str]


class AgentRequestData(MessageData):
    """Data payload for agent request messages."""
    chat_messages: List[ChatMessage]
    timeout: Optional[float]
    

class AgentResponseData(MessageData):
    """Data payload for agent response messages."""
    message: str
    agent: str
    

class StreamChunkData(MessageData):
    """Data payload for streaming chunk messages."""
    chunk: str
    chunk_index: int
    message_id: str
    

class StreamEndData(MessageData):
    """Data payload for stream end messages."""
    message_id: str
    final_content: str
    

class AuditEventData(TypedDict):
    """Data payload for audit events."""
    message_id: str
    message_type: str
    message_source: str
    channel: str
    category: AuditCategory
    audit_timestamp: str
    content: Optional[str]
    error: Optional[Dict[str, str]]


# Message type definitions
class MessageDict(TypedDict, total=False):
    """Base message dictionary structure."""
    id: str
    type: str
    source: str
    data: Dict[str, Any]
    specversion: str
    datacontenttype: str
    subject: Optional[str]
    time: Optional[str]
    traceparent: Optional[str]
    tracestate: Optional[str]
    service_tier: Optional[str]


# Specific message types for each domain
class AuditLogMessage(TypedDict):
    """Audit log message structure."""
    id: str
    type: Literal[MessageType.AUDIT_LOG]
    source: Union[Literal[AgentName.AUDIT], Literal[AgentName.AUDIT_AGENT]]
    data: AuditEventData
    traceparent: Optional[str]
    tracestate: Optional[str]


class BillingRequestMessage(TypedDict):
    """Billing request message structure."""
    id: str
    type: Literal[MessageType.BILLING_REQUEST]
    source: str  # Usually AgentName.TRIAGE
    data: AgentRequestData
    traceparent: Optional[str]
    tracestate: Optional[str]


class ClaimRequestMessage(TypedDict):
    """Claim request message structure."""
    id: str
    type: Literal[MessageType.CLAIM_REQUEST]
    source: str  # Usually AgentName.TRIAGE
    data: AgentRequestData
    traceparent: Optional[str]
    tracestate: Optional[str]


class PolicyRequestMessage(TypedDict):
    """Policy request message structure."""
    id: str
    type: Literal[MessageType.POLICY_REQUEST]
    source: str  # Usually AgentName.TRIAGE
    data: AgentRequestData
    traceparent: Optional[str]
    tracestate: Optional[str]


class EscalationRequestMessage(TypedDict):
    """Escalation request message structure."""
    id: str
    type: Literal[MessageType.ESCALATION_REQUEST]
    source: str  # Usually AgentName.TRIAGE
    data: AgentRequestData
    traceparent: Optional[str]
    tracestate: Optional[str]


class UserMessage(TypedDict):
    """User message from frontend."""
    id: str
    type: Literal[MessageType.USER_MESSAGE]
    source: Literal[AgentName.FRONTEND]
    data: AgentRequestData
    traceparent: Optional[str]
    tracestate: Optional[str]


class AgentMessage(TypedDict):
    """Agent response message."""
    id: str
    type: Literal[MessageType.AGENT_MESSAGE]
    source: str  # Agent name: AgentName.BILLING, AgentName.CLAIMS, etc.
    data: AgentResponseData
    traceparent: Optional[str]
    tracestate: Optional[str]


class StreamChunkMessage(TypedDict):
    """Streaming chunk message."""
    id: str
    type: Literal[MessageType.AGENT_MESSAGE_STREAM_CHUNK]
    source: str  # Agent name
    data: StreamChunkData
    traceparent: Optional[str]
    tracestate: Optional[str]


class StreamEndMessage(TypedDict):
    """Stream end message."""
    id: str
    type: Literal[MessageType.AGENT_MESSAGE_STREAM_END]
    source: str  # Agent name
    data: StreamEndData
    traceparent: Optional[str]
    tracestate: Optional[str]


# Union of all message types
SpecificMessage = Union[
    AuditLogMessage,
    BillingRequestMessage,
    ClaimRequestMessage,
    PolicyRequestMessage,
    EscalationRequestMessage,
]


# Filter protocol
T = TypeVar('T', bound=MessageDict)


class MessageFilter(Protocol[T]):
    """Protocol for message filter functions."""
    def __call__(self, msg: T) -> bool: ...


# Type guards
def is_audit_log(msg: Dict[str, Any]) -> TypeGuard[AuditLogMessage]:
    """Type guard for audit log messages."""
    return (
        msg.get("type") == MessageType.AUDIT_LOG and 
        msg.get("source") in [AgentName.AUDIT, AgentName.AUDIT_AGENT]
    )


def is_billing_request(msg: Dict[str, Any]) -> TypeGuard[BillingRequestMessage]:
    """Type guard for billing request messages."""
    return msg.get("type") == MessageType.BILLING_REQUEST


def is_claim_request(msg: Dict[str, Any]) -> TypeGuard[ClaimRequestMessage]:
    """Type guard for claim request messages."""
    return msg.get("type") == MessageType.CLAIM_REQUEST


def is_policy_request(msg: Dict[str, Any]) -> TypeGuard[PolicyRequestMessage]:
    """Type guard for policy request messages."""
    return msg.get("type") == MessageType.POLICY_REQUEST


def is_escalation_request(msg: Dict[str, Any]) -> TypeGuard[EscalationRequestMessage]:
    """Type guard for escalation request messages."""
    return msg.get("type") == MessageType.ESCALATION_REQUEST


def is_user_message(msg: Dict[str, Any]) -> TypeGuard[UserMessage]:
    """Type guard for user messages."""
    return (
        msg.get("type") == MessageType.USER_MESSAGE and
        msg.get("source") == AgentName.FRONTEND
    )


def is_agent_message(msg: Dict[str, Any]) -> TypeGuard[AgentMessage]:
    """Type guard for agent response messages."""
    return msg.get("type") == MessageType.AGENT_MESSAGE


def is_stream_end(msg: Dict[str, Any]) -> TypeGuard[StreamEndMessage]:
    """Type guard for stream end messages."""
    return msg.get("type") == MessageType.AGENT_MESSAGE_STREAM_END


# Filter factories
def create_type_filter(message_type: Union[str, MessageType]) -> MessageFilter[MessageDict]:
    """Create a type-safe message filter for a specific message type."""
    return lambda msg: msg.get("type") == message_type


def create_source_filter(source: Union[str, AgentName]) -> MessageFilter[MessageDict]:
    """Create a type-safe message filter for a specific source."""
    return lambda msg: msg.get("source") == source


def create_compound_filter(
    message_type: Optional[Union[str, MessageType]] = None,
    source: Optional[Union[str, AgentName]] = None,
) -> MessageFilter[MessageDict]:
    """Create a compound filter for multiple criteria."""
    def filter_func(msg: Dict[str, Any]) -> bool:
        if message_type and msg.get("type") != message_type:
            return False
        if source and msg.get("source") != source:
            return False
        return True
    return filter_func


# Typed subscribe wrapper
HandlerT = TypeVar('HandlerT', bound=Callable)


class SubscribeConfig(TypedDict, total=False):
    """Configuration options for subscribe decorator."""
    filter_by_message: MessageFilter
    group_id: str
    auto_offset_reset: OffsetReset
    enable_auto_commit: bool
    max_poll_records: int
    max_poll_interval_ms: int


def subscribe(
    agent: Agent,
    channel: Channel,
    *,
    message_type: Optional[Union[str, MessageType]] = None,
    source: Optional[Union[str, AgentName]] = None,
    filter_func: Optional[MessageFilter] = None,
    group_id: Optional[str] = None,
    auto_offset_reset: Union[OffsetReset, Literal["latest", "earliest", "none"]] = OffsetReset.LATEST,
    **kwargs: Any
) -> Callable[[HandlerT], HandlerT]:
    """
    Type-safe wrapper for agent.subscribe with better parameter hints.
    
    Args:
        agent: The agent instance
        channel: Channel to subscribe to
        message_type: Filter by specific message type
        source: Filter by specific source
        filter_func: Custom filter function (overrides message_type/source)
        group_id: Kafka consumer group ID
        auto_offset_reset: Where to start consuming
        **kwargs: Additional Kafka consumer options
    
    Returns:
        Decorator function
    """
    # Build filter function
    if not filter_func:
        if message_type or source:
            filter_func = create_compound_filter(message_type, source)
    
    # Build subscribe kwargs
    subscribe_kwargs: Dict[str, Any] = {
        "auto_offset_reset": auto_offset_reset,
        **kwargs
    }
    
    if filter_func:
        subscribe_kwargs["filter_by_message"] = filter_func
    
    if group_id:
        subscribe_kwargs["group_id"] = group_id
    
    return agent.subscribe(channel=channel, **subscribe_kwargs)


# Alias for backward compatibility
typed_subscribe = subscribe


# Export all the important types and enums
__all__ = [
    # Enums
    "MessageType",
    "AgentName", 
    "AuditCategory",
    "OffsetReset",
    
    # Data payload types
    "MessageData",
    "ChatMessage",
    "AgentRequestData",
    "AgentResponseData",
    "StreamChunkData",
    "StreamEndData",
    "AuditEventData",
    
    # Message types
    "AuditLogMessage",
    "BillingRequestMessage",
    "ClaimRequestMessage",
    "PolicyRequestMessage",
    "EscalationRequestMessage",
    "UserMessage",
    "AgentMessage",
    "StreamChunkMessage",
    "StreamEndMessage",
    
    # Type guards
    "is_audit_log",
    "is_billing_request",
    "is_claim_request",
    "is_policy_request",
    "is_escalation_request",
    "is_user_message",
    "is_agent_message",
    "is_stream_end",
    
    # Filter factories
    "create_type_filter",
    "create_source_filter",
    "create_compound_filter",
    
    # Main functions
    "subscribe",
    "typed_subscribe",
    
    # Handler types
    "BillingHandler",
    "ClaimsHandler",
    "PolicyHandler",
    "EscalationHandler",
    "UserMessageHandler",
    "AuditHandler",
]


# Typed handler signatures for better IDE support
BillingHandler = Callable[[Union[BillingRequestMessage, TracedMessage], KafkaMessage], None]
ClaimsHandler = Callable[[Union[ClaimRequestMessage, TracedMessage], KafkaMessage], None]
PolicyHandler = Callable[[Union[PolicyRequestMessage, TracedMessage], KafkaMessage], None]
EscalationHandler = Callable[[Union[EscalationRequestMessage, TracedMessage], KafkaMessage], None]
UserMessageHandler = Callable[[Union[UserMessage, TracedMessage], KafkaMessage], None]
AuditHandler = Callable[[Union[TracedMessage, Dict], KafkaMessage], Optional[Union[TracedMessage, Dict]]]


