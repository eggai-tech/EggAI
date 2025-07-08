"""
Agent messaging utilities.

Provides the @subscribe decorator for type-safe message subscriptions.
For protocol documentation, see libraries/protocol/README.md
"""

from typing import (
    Any,
    Callable,
    Dict,
    Literal,
    Optional,
    Protocol,
    TypedDict,
    TypeVar,
    Union,
)

from eggai import Agent, Channel
from faststream.kafka import KafkaMessage

# Import all protocol definitions
from libraries.communication.protocol import (
    AgentName,
    BillingRequestMessage,
    ClaimRequestMessage,
    EscalationRequestMessage,
    # Data types
    MessageType,
    OffsetReset,
    PolicyRequestMessage,
    UserMessage,
)
from libraries.observability.tracing import TracedMessage

# Filter protocol
T = TypeVar('T', bound=Dict[str, Any])


class MessageFilter(Protocol[T]):
    """Protocol for message filter functions."""
    def __call__(self, msg: T) -> bool: ...


# Filter factories
def create_type_filter(message_type: Union[str, MessageType]) -> MessageFilter[Dict[str, Any]]:
    """Create a type-safe message filter for a specific message type."""
    return lambda msg: msg.get("type") == message_type


def create_source_filter(source: Union[str, AgentName]) -> MessageFilter[Dict[str, Any]]:
    """Create a type-safe message filter for a specific source."""
    return lambda msg: msg.get("source") == source


def create_compound_filter(
    message_type: Optional[Union[str, MessageType]] = None,
    source: Optional[Union[str, AgentName]] = None,
) -> MessageFilter[Dict[str, Any]]:
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
    Type-safe wrapper for agent.subscribe.
    
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


# Export only what's defined in this module
__all__ = [
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


