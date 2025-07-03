from typing import Dict, Optional, Union
from uuid import uuid4

from eggai import Agent, Channel
from faststream.kafka import KafkaMessage

from libraries.channels import channels
from libraries.logger import get_console_logger
from libraries.tracing import TracedMessage, create_tracer, traced_handler
from libraries.tracing.init_metrics import init_token_metrics
from libraries.tracing.otel import safe_set_attribute

from .config import settings
from .types import AuditCategory, AuditConfig, AuditEvent

tracer = create_tracer("audit_agent")

init_token_metrics(
    port=settings.prometheus_metrics_port, application_name=settings.app_name
)

MESSAGE_CATEGORIES: Dict[str, AuditCategory] = {
    "agent_message": "User Communication",
    "billing_request": "Billing",
    "policy_request": "Policies",
    "escalation_request": "Escalation",
    "triage_request": "Triage",
}

audit_config = AuditConfig(
    message_categories=MESSAGE_CATEGORIES,
    default_category="Other",
    enable_debug_logging=settings.debug_logging_enabled,
    audit_channel_name=channels.audit_logs,
)

audit_agent = Agent("AuditAgent")
logger = get_console_logger("audit_agent")

agents_channel = Channel(channels.agents)
human_channel = Channel(channels.human)
audit_logs_channel = Channel(channels.audit_logs)


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

    # Fallback to dict-like access
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
    """Return the message ID or a new UUID for unknown messages."""
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


@audit_agent.subscribe(channel=agents_channel)
@audit_agent.subscribe(channel=human_channel)
@traced_handler("audit_message")
async def audit_message(
    message: Union[TracedMessage, Dict], msg: KafkaMessage
) -> Optional[Union[TracedMessage, Dict]]:
    try:
        channel = msg.raw_message.topic
        message_type, source = get_message_metadata(message)
        message_id = get_message_id(message)
        category: AuditCategory = audit_config.message_categories.get(
            message_type, audit_config.default_category
        )

        with tracer.start_as_current_span("process_audit_message") as span:
            safe_set_attribute(span, "audit.channel", channel)
            safe_set_attribute(span, "audit.message_type", message_type)
            safe_set_attribute(span, "audit.source", source)
            safe_set_attribute(span, "audit.category", category)
            safe_set_attribute(span, "audit.message_id", message_id)

            if audit_config.enable_debug_logging:
                logger.info(
                    f"AuditAgent: category={category}, channel={channel}, "
                    f"type={message_type}, source={source}, id={message_id}"
                )
            else:
                logger.debug(
                    f"AuditAgent: category={category}, channel={channel}, "
                    f"type={message_type}, source={source}, id={message_id}"
                )

            # build standardized audit log
            audit_event = AuditEvent(
                message_id=message_id,
                message_type=message_type,
                message_source=source,
                channel=channel,
                category=category,
                content=get_message_content(message),
            )
            data = audit_event.to_dict()

            log_message = TracedMessage(
                id=str(uuid4()),
                type="audit_log",
                source=audit_agent.name,
                data=data,
            )
            propagate_trace_context(message, log_message)
            await audit_logs_channel.publish(log_message)

        return message

    except Exception as e:
        logger.error(f"Error processing audit message: {e}", exc_info=True)
        return message
