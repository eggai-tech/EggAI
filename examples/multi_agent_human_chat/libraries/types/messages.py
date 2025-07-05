from typing import Any, Dict, List, Optional, TypedDict


class ChatMessage(TypedDict, total=False):
    content: str
    role: str
    # Optional fields that some agents may use
    id: Optional[str]
    agent: Optional[str]


class MessageData(TypedDict, total=False):
    chat_messages: List[ChatMessage]
    connection_id: str
    message_id: str
    # Optional fields used by some agents
    session: Optional[str]
    message: Optional[str]
    agent: Optional[str]


class TracedMessageDict(TypedDict, total=False):
    id: str
    type: str
    source: str
    data: Dict[str, Any]
    traceparent: Optional[str]
    tracestate: Optional[str]