"""Audit Agent module for capturing messages from human and agent channels
and publishing standardized audit logs."""
__all__ = [
    "audit_agent",
    "audit_message",
]

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
from .types import MESSAGE_CATEGORIES, AuditCategory, AuditConfig, AuditEvent
from .utils import (
    get_message_content,
    get_message_id,
    get_message_metadata,
    propagate_trace_context,
)

tracer = create_tracer("audit_agent")

init_token_metrics(
    port=settings.prometheus_metrics_port, application_name=settings.app_name
)


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


@audit_agent.subscribe(channel=agents_channel)
@audit_agent.subscribe(channel=human_channel)
@traced_handler("audit_message")
async def audit_message(
    message: Union[TracedMessage, Dict], msg: KafkaMessage
) -> Optional[Union[TracedMessage, Dict]]:
    channel = msg.raw_message.topic
    message_type, source = get_message_metadata(message)
    message_id = get_message_id(message)
    category: AuditCategory = audit_config.message_categories.get(
        message_type, audit_config.default_category
    )

    try:
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
                source=audit_agent._name,
                data=data,
            )
            propagate_trace_context(message, log_message)
            await audit_logs_channel.publish(log_message)
    except Exception as e:
        logger.error("Error processing audit message", exc_info=True)
        # emit error audit entry
        error_event = AuditEvent(
            message_id=message_id,
            message_type=message_type,
            message_source=source,
            channel=channel,
            category="Error",
            error={"type": type(e).__name__, "message": str(e)},
        )
        data_err = error_event.to_dict()
        log_error = TracedMessage(
            id=str(uuid4()), type="audit_log", source=audit_agent._name, data=data_err
        )
        propagate_trace_context(message, log_error)
        await audit_logs_channel.publish(log_error)

    return message
