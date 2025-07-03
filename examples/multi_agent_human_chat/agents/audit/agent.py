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
from .types import AuditCategory, AuditConfig

logger = get_console_logger("audit_agent")

agents_channel = Channel("agents")
human_channel = Channel("human")
audit_logs_channel = Channel("audit_logs")
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
    message: Optional[Union[TracedMessage, Dict]],
) -> tuple[str, str]:
    if message is None:
        return "unknown", "unknown"

    if hasattr(message, "type") and hasattr(message, "source"):
        return message.type, message.source

    try:
        return message.get("type", "unknown"), message.get("source", "unknown")
    except (AttributeError, TypeError):
        logger.warning("Message has no type or source attributes and is not dict-like")
        return "unknown", "unknown"


def get_message_content(message: Optional[Union[TracedMessage, Dict]]) -> Optional[str]:
    """Extract message content from various message formats."""
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
                    # Get the last user message from chat history
                    last_msg = data["chat_messages"][-1]
                    if isinstance(last_msg, dict) and "content" in last_msg:
                        return last_msg["content"]
        return None
    except (AttributeError, TypeError, IndexError):
        logger.warning("Could not extract message content", exc_info=True)
        return None


def get_message_id(message: Optional[Union[TracedMessage, Dict]]) -> str:
    if message is None:
        return f"null_message_{uuid4()}"
    return str(getattr(message, "id", uuid4()))


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

            await audit_logs_channel.publish(message)

        return message

    except Exception as e:
        logger.error(f"Error processing audit message: {e}", exc_info=True)
        return message
