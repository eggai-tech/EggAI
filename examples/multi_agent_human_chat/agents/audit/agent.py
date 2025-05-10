from datetime import datetime
from uuid import uuid4

from eggai import Agent, Channel
from eggai.transport import eggai_set_default_transport
from faststream.kafka import KafkaMessage

from libraries.kafka_transport import create_kafka_transport
from libraries.logger import get_console_logger
from libraries.tracing import TracedMessage, create_tracer, traced_handler

from .config import settings

eggai_set_default_transport(
    lambda: create_kafka_transport(
        bootstrap_servers=settings.kafka_bootstrap_servers,
        ssl_cert=settings.kafka_ca_content
    )
)

agents_channel = Channel("agents")
human_channel = Channel("human")
audit_logs_channel = Channel("audit_logs")

logger = get_console_logger("audit_agent")
tracer = create_tracer("audit_agent")

MESSAGE_CATEGORIES = {
    "agent_message": "User Communication",
    "billing_request": "Billing",
    "policy_request": "Policies",
    "escalation_request": "Escalation",
    "triage_request": "Triage",
}

audit_agent = Agent("AuditAgent")

async def get_channel(msg):
    try:
        return msg.path.get("channel", "unknown_channel") if msg and hasattr(msg, "path") else "unknown_channel"
    except (AttributeError, KeyError, TypeError):
        logger.warning("Could not get channel from Kafka message")
        return "unknown_channel"

def get_message_metadata(message):
    if message is None:
        return "unknown", "unknown"
        
    if hasattr(message, 'type') and hasattr(message, 'source'):
        return message.type, message.source
        
    try:
        return message.get("type", "unknown"), message.get("source", "unknown")
    except (AttributeError, TypeError):
        logger.warning("Message has no type or source attributes and is not dict-like")
        return "unknown", "unknown"

def get_message_id(message):
    if message is None:
        return "null_message_" + str(uuid4())
    return str(getattr(message, 'id', uuid4()))

def propagate_trace_context(source_message, target_message):
    if source_message is None:
        return
        
    if hasattr(source_message, 'traceparent') and source_message.traceparent:
        target_message.traceparent = source_message.traceparent
    if hasattr(source_message, 'tracestate') and source_message.tracestate:
        target_message.tracestate = source_message.tracestate

async def publish_audit_event(message_id, message_type, source, channel, category, message=None, error=None):
    audit_data = {
        "message_id": message_id,
        "message_type": message_type,
        "message_source": source,
        "channel": channel,
        "category": category,
        "audit_timestamp": datetime.now().isoformat()
    }
    
    if error:
        audit_data["error"] = error
    
    audit_event = TracedMessage(
        id=str(uuid4()),
        type="audit_log",
        source="AuditAgent",
        data=audit_data
    )
    
    propagate_trace_context(message, audit_event)
    
    try:
        await audit_logs_channel.publish(audit_event)
    except Exception as e:
        logger.error(f"Failed to publish audit event: {e}")

@audit_agent.subscribe(channel=agents_channel)
@audit_agent.subscribe(channel=human_channel)
@traced_handler("audit_message")
async def audit_message(message, msg: KafkaMessage):
    try:
        channel = await get_channel(msg)
        
        if message is None:
            logger.warning("Received null message for auditing")
            await publish_audit_event(
                message_id="null_message_" + str(uuid4()),
                message_type="null",
                source="unknown",
                channel=channel,
                category="Error",
                error={
                    "type": "null_message",
                    "description": "Received null message for auditing"
                }
            )
            return None
        
        message_type, source = get_message_metadata(message)
        category = MESSAGE_CATEGORIES.get(message_type, "Other")
        message_id = get_message_id(message)
        
        try:
            with tracer.start_as_current_span("process_audit_message") as span:
                span.set_attribute("audit.channel", channel)
                span.set_attribute("audit.message_type", message_type)
                span.set_attribute("audit.source", source)
                span.set_attribute("audit.category", category)

                logger.info(
                    f"AuditAgent: category={category}, channel={channel}, "
                    f"type={message_type}, source={source}, content={message}"
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
            logger.error(f"Error creating span for audit: {span_error}")
            
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
                error={
                    "type": "span_creation_error",
                    "message": str(span_error)
                }
            )

        return message
    except Exception as e:
        logger.error(f"Error processing audit message: {e}", exc_info=True)
        return message
