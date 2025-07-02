import asyncio
from typing import Dict, Optional, Union

from eggai import Agent, Channel
from eggai.transport import eggai_set_default_transport
from faststream.kafka import KafkaMessage

from libraries.channels import channels
from libraries.kafka_transport import create_kafka_transport
from libraries.logger import get_console_logger
from libraries.trace_utils import get_message_id, get_message_metadata
from libraries.tracing import TracedMessage, get_tracer, traced_handler
from libraries.tracing.init_metrics import init_token_metrics
from libraries.tracing.otel import safe_set_attribute

from .config import settings
from .types import AuditCategory, AuditConfig

eggai_set_default_transport(
    lambda: create_kafka_transport(
        bootstrap_servers=settings.kafka_bootstrap_servers,
        ssl_cert=settings.kafka_ca_content,
    )
)
logger = get_console_logger("audit_agent")
tracer = get_tracer("audit_agent")

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

agents_channel = Channel(channels.agents)
human_channel = Channel(channels.human)
audit_logs_channel = Channel(channels.audit_logs)


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

    except (KeyError, ValueError) as exc:
        logger.warning("Invalid audit message: %s", exc, exc_info=True)
        return message
    except (ConnectionError, asyncio.TimeoutError) as exc:
        logger.error("Network error processing audit message: %s", exc, exc_info=True)
        return message
    except Exception as exc:
        logger.error(
            "Unexpected error processing audit message: %s", exc, exc_info=True
        )
        return message
