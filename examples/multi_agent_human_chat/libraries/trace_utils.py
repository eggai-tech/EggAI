"""Utility helpers for working with traced messages."""

from __future__ import annotations

from typing import Dict, Optional, Union
from uuid import uuid4

from libraries.tracing import TracedMessage


def get_message_metadata(message: Optional[Union[TracedMessage, Dict]]) -> tuple[str, str]:
    """Return the type and source of a message, falling back to ``"unknown"``."""
    if message is None:
        return "unknown", "unknown"

    if hasattr(message, "type") and hasattr(message, "source"):
        return message.type, message.source

    try:
        return message.get("type", "unknown"), message.get("source", "unknown")
    except (AttributeError, TypeError):
        return "unknown", "unknown"


def get_message_content(message: Optional[Union[TracedMessage, Dict]]) -> Optional[str]:
    """Extract the message content from a ``TracedMessage`` or mapping."""
    if message is None:
        return None

    try:
        if hasattr(message, "data"):
            data = message.data
            if isinstance(data, dict):
                if "message" in data:
                    return data["message"]
                if (
                    "chat_messages" in data
                    and isinstance(data["chat_messages"], list)
                    and data["chat_messages"]
                ):
                    last_msg = data["chat_messages"][-1]
                    if isinstance(last_msg, dict) and "content" in last_msg:
                        return last_msg["content"]
        return None
    except (AttributeError, TypeError, IndexError):
        return None


def get_message_id(message: Optional[Union[TracedMessage, Dict]]) -> str:
    """Return the message ID or generate a random one for ``None``."""
    if message is None:
        return f"null_message_{uuid4()}"
    return str(getattr(message, "id", uuid4()))


def propagate_trace_context(
    source_message: Optional[Union[TracedMessage, Dict]],
    target_message: TracedMessage,
) -> None:
    """Copy trace context from ``source_message`` to ``target_message`` if present."""
    if source_message is None:
        return

    if hasattr(source_message, "traceparent") and source_message.traceparent:
        target_message.traceparent = source_message.traceparent
    if hasattr(source_message, "tracestate") and source_message.tracestate:
        target_message.tracestate = source_message.tracestate
