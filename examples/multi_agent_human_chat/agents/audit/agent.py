from faststream.kafka import KafkaMessage
from typing import Dict, Any, Optional
from eggai import Channel, Agent
from eggai.transport import KafkaTransport, eggai_set_default_transport
from libraries.logger import get_console_logger
from libraries.tracing import TracedMessage, traced_handler, create_tracer, format_span_as_traceparent
from opentelemetry import trace
from .config import settings

eggai_set_default_transport(lambda: KafkaTransport(bootstrap_servers=settings.kafka_bootstrap_servers))

agents_channel = Channel("agents")
human_channel = Channel("human")

logger = get_console_logger("audit_agent")
tracer = create_tracer("audit_agent")

# Message type categories
MESSAGE_CATEGORIES = {
    "agent_message": "User Communication",
    "billing_request": "Billing",
    "policy_request": "Policies",
    "escalation_request": "Escalation",
    "triage_request": "Triage",
    # Add more categorizations as needed
}

audit_agent = Agent("AuditAgent")

@audit_agent.subscribe(pattern="{channel}")
@traced_handler("audit_message")
def audit_message(message, msg: KafkaMessage):
    try:
        # Extract message details
        channel = msg.path
        message_type = message.get("type", "unknown")
        source = message.get("source", "unknown")
        
        # Categorize the message
        category = MESSAGE_CATEGORIES.get(message_type, "Other")
        
        # Create a detailed audit log
        with tracer.start_as_current_span("process_audit_message") as span:
            span.set_attribute("audit.channel", channel)
            span.set_attribute("audit.message_type", message_type)
            span.set_attribute("audit.source", source)
            span.set_attribute("audit.category", category)
            
            # Log with categorization
            logger.info(
                f"AuditAgent received message: category={category}, channel={channel}, " 
                f"type={message_type}, source={source}, content={message}"
            )
            
            # Here you could add persistent storage logic in the future
        
        return message
    except Exception as e:
        logger.error(f"Error processing audit message: {e}", exc_info=True)
        # Still return the message to not disrupt message flow
        return message