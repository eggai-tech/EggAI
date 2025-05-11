from datetime import datetime
from typing import Dict, Optional, Union
from uuid import uuid4

from eggai import Agent, Channel
from eggai.transport import eggai_set_default_transport
from faststream.kafka import KafkaMessage

from libraries.kafka_transport import create_kafka_transport
from libraries.logger import get_console_logger
from libraries.tracing import TracedMessage, create_tracer, traced_handler
from libraries.tracing.otel import safe_set_attribute

from .config import settings
from .types import AuditCategory, AuditConfig, AuditEvent

eggai_set_default_transport(
    lambda: create_kafka_transport(
        bootstrap_servers=settings.kafka_bootstrap_servers,
        ssl_cert=settings.kafka_ca_content
    )
)
logger = get_console_logger("audit_agent")

agents_channel = Channel("agents")
human_channel = Channel("human")
audit_logs_channel = Channel("audit_logs")
tracer = create_tracer("audit_agent")

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
    audit_channel_name="audit_logs"
)

audit_agent = Agent("AuditAgent")


async def get_channel(msg: Optional[KafkaMessage]) -> str:
    try:
        return msg.path.get("channel", "unknown_channel") if msg and hasattr(msg, "path") else "unknown_channel"
    except (AttributeError, KeyError, TypeError):
        logger.warning("Could not get channel from Kafka message")
        return "unknown_channel"


def get_message_metadata(message: Optional[Union[TracedMessage, Dict]]) -> tuple[str, str]:
    if message is None:
        return "unknown", "unknown"
        
    if hasattr(message, 'type') and hasattr(message, 'source'):
        return message.type, message.source
        
    try:
        return message.get("type", "unknown"), message.get("source", "unknown")
    except (AttributeError, TypeError):
        logger.warning("Message has no type or source attributes and is not dict-like")
        return "unknown", "unknown"


def get_message_id(message: Optional[Union[TracedMessage, Dict]]) -> str:
    if message is None:
        return f"null_message_{uuid4()}"
    return str(getattr(message, 'id', uuid4()))


def propagate_trace_context(source_message: Optional[Union[TracedMessage, Dict]], target_message: TracedMessage) -> None:
    if source_message is None:
        return
        
    if hasattr(source_message, 'traceparent') and source_message.traceparent:
        target_message.traceparent = source_message.traceparent
    if hasattr(source_message, 'tracestate') and source_message.tracestate:
        target_message.tracestate = source_message.tracestate


async def publish_audit_event(
    message_id: str,
    message_type: str,
    source: str,
    channel: str,
    category: AuditCategory,
    message: Optional[Union[TracedMessage, Dict]] = None,
    error: Optional[Dict[str, str]] = None
) -> None:
    audit_event_data = AuditEvent(
        message_id=message_id,
        message_type=message_type,
        message_source=source,
        channel=channel,
        category=category,
        audit_timestamp=datetime.now(),
        error=error
    )
    
    audit_event = TracedMessage(
        id=str(uuid4()),
        type="audit_log",
        source="AuditAgent",
        data=audit_event_data.to_dict()
    )
    
    propagate_trace_context(message, audit_event)
    
    try:
        await audit_logs_channel.publish(audit_event)
        if audit_config.enable_debug_logging:
            logger.debug(f"Published audit event: {message_id}")
    except Exception as e:
        logger.error(f"Failed to publish audit event: {e}", exc_info=True)


@audit_agent.subscribe(channel=agents_channel)
@audit_agent.subscribe(channel=human_channel)
@traced_handler("audit_message")
async def audit_message(message: Union[TracedMessage, Dict], msg: KafkaMessage) -> Optional[Union[TracedMessage, Dict]]:
    try:
        channel = await get_channel(msg)
        
        if message is None:
            logger.warning("Received null message for auditing")
            await publish_audit_event(
                message_id=f"null_message_{uuid4()}",
                message_type="null",
                source="unknown",
                channel=channel,
                category="Error",
                error={"type": "null_message", "description": "Received null message for auditing"}
            )
            return None
        
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
                
                await publish_audit_event(
                    message_id=message_id,
                    message_type=message_type,
                    source=source,
                    channel=channel,
                    category=category,
                    message=message
                )
                
        except Exception as span_error:
            logger.error(f"Error creating span for audit: {span_error}", exc_info=True)
            
            logger.info(
                f"AuditAgent (no span): category={category}, channel={channel}, "
                f"type={message_type}, source={source}"
            )
            
            await publish_audit_event(
                message_id=message_id,
                message_type=message_type,
                source=source,
                channel=channel,
                category=category,
                message=message,
                error={"type": "span_creation_error", "message": str(span_error)}
            )

        return message
        
    except Exception as e:
        logger.error(f"Error processing audit message: {e}", exc_info=True)
        
        try:
            await publish_audit_event(
                message_id=get_message_id(message) if message is not None else f"error_{uuid4()}",
                message_type="error",
                source="AuditAgent",
                channel=await get_channel(msg),
                category="Error",
                message=message,
                error={"type": "processing_error", "message": str(e)}
            )
        except Exception as nested_error:
            logger.error(f"Failed to publish error audit: {nested_error}", exc_info=True)
            
        return message