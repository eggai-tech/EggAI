from typing import Dict, Optional, Union
from uuid import uuid4

from libraries.logger import get_console_logger
from libraries.tracing import TracedMessage

logger = get_console_logger("audit_agent")

def get_message_metadata(
    message: Optional[Union[TracedMessage, Dict]]
) -> tuple[str, str]:
    """Return (type, source) from a message, defaulting to 'unknown'."""
    if message is None:
        return "unknown", "unknown"

    mtype = getattr(message, "type", None)
    msource = getattr(message, "source", None)
    if mtype is not None or msource is not None:
        return mtype or "unknown", msource or "unknown"

    try:
        return message.get("type", "unknown"), message.get("source", "unknown")
    except Exception:
        logger.warning("Could not extract message type/source from %r", message)
        return "unknown", "unknown"


def get_message_content(message: Optional[Union[TracedMessage, Dict]]) -> Optional[str]:
    """Extract the primary message text or last chat history content."""
    data = getattr(message, "data", None)
    if not isinstance(data, dict):
        return None

    content = data.get("message")
    if isinstance(content, str):
        return content

    chat = data.get("chat_messages")
    if isinstance(chat, list) and chat:
        last = chat[-1]
        if isinstance(last, dict):
            return last.get("content")

    return None


def get_message_id(message: Optional[Union[TracedMessage, Dict]]) -> str:
    if message is None:
        return f"null_message_{uuid4()}"

    mid = getattr(message, "id", None)
    return str(mid) if mid is not None else str(uuid4())


def propagate_trace_context(
    source_message: Optional[Union[TracedMessage, Dict]], target_message: TracedMessage
) -> None:
    if source_message is None:
        return

    if hasattr(source_message, "traceparent") and source_message.traceparent:
        target_message.traceparent = source_message.traceparent
    if hasattr(source_message, "tracestate") and source_message.tracestate:
        target_message.tracestate = source_message.tracestate