import asyncio
from typing import List

from eggai import Agent, Channel
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

from agents.policies.agent.react import policies_react_dspy
from agents.policies.config import settings
from agents.policies.types import ChatMessage, ModelConfig
from libraries.channels import channels
from libraries.logger import get_console_logger
from libraries.streaming_agent import format_conversation, process_request_stream
from libraries.tracing import (
    TracedMessage,
    get_tracer,
    traced_handler,
)
from libraries.tracing.init_metrics import init_token_metrics
from libraries.tracing.otel import safe_set_attribute

policies_agent = Agent(name="PoliciesAgent")
logger = get_console_logger("policies_agent.handler")
agents_channel = Channel(channels.agents)
human_channel = Channel(channels.human)
human_stream_channel = Channel(channels.human_stream)
tracer = get_tracer("policies_agent")

init_token_metrics(
    port=settings.prometheus_metrics_port, application_name=settings.app_name
)


def get_conversation_string(chat_messages: List[ChatMessage]) -> str:
    """Legacy wrapper for tests that formats chat history."""
    return format_conversation(chat_messages, tracer=tracer, logger=logger)

async def process_policy_request(
    conversation_string: str,
    connection_id: str,
    message_id: str,
    timeout_seconds: float = None,
) -> None:
    """Generate a response to a policy request with streaming output."""
    # Create model config with timeout value
    config = ModelConfig(timeout_seconds=timeout_seconds or 30.0)
    with tracer.start_as_current_span("process_policy_request") as span:
        carrier = {}
        TraceContextTextMapPropagator().inject(carrier)
        child_traceparent = carrier.get("traceparent")
        child_tracestate = carrier.get("tracestate", "")
        safe_set_attribute(span, "connection_id", connection_id)
        safe_set_attribute(span, "message_id", message_id)
        safe_set_attribute(span, "conversation_length", len(conversation_string))
        safe_set_attribute(span, "timeout_seconds", config.timeout_seconds)

        if (
            not conversation_string
            or len(conversation_string.strip()) < settings.min_conversation_length
        ):
            safe_set_attribute(span, "error", "Empty or too short conversation")
            span.set_status(1, "Invalid input")
            raise ValueError("Conversation history is too short to process")

        logger.info("Calling policies model with streaming")
        chunks = policies_react_dspy(chat_history=conversation_string, config=config)

        await process_request_stream(
            chunks,
            agent_name="PoliciesAgent",
            connection_id=connection_id,
            message_id=message_id,
            human_stream_channel=human_stream_channel,
            tracer=tracer,
            logger=logger,
            child_traceparent=child_traceparent,
            child_tracestate=child_tracestate,
        )


@policies_agent.subscribe(
    channel=agents_channel,
    filter_by_message=lambda msg: msg.get("type") == "policy_request",
    auto_offset_reset="latest",
    group_id="policies_agent_group",
)
@traced_handler("handle_policy_request")
async def handle_policy_request(msg: TracedMessage) -> None:
    """Handle incoming policy request messages from the agents channel."""
    connection_id = msg.data.get("connection_id", "unknown")
    try:
        chat_messages: List[ChatMessage] = msg.data.get("chat_messages", [])

        if not chat_messages:
            logger.warning(f"Empty chat history for connection: {connection_id}")
            carrier = {}
            TraceContextTextMapPropagator().inject(carrier)
            await human_channel.publish(
                TracedMessage(
                    type="agent_message",
                    source="PoliciesAgent",
                    data={
                        "message": "I apologize, but I didn't receive any message content to process.",
                        "connection_id": connection_id,
                        "agent": "PoliciesAgent",
                    },
                    traceparent=carrier.get("traceparent"),
                    tracestate=carrier.get("tracestate", ""),
                )
            )
            return

        conversation_string = get_conversation_string(chat_messages)
        logger.info(f"Processing policy request for connection {connection_id}")

        await process_policy_request(
            conversation_string, connection_id, str(msg.id), timeout_seconds=30.0
        )

    except ValueError as exc:
        logger.warning("Invalid policies request: %s", exc, exc_info=True)
        carrier = {}
        TraceContextTextMapPropagator().inject(carrier)
        await human_channel.publish(
            TracedMessage(
                type="agent_message",
                source="PoliciesAgent",
                data={
                    "message": str(exc),
                    "connection_id": connection_id,
                    "agent": "PoliciesAgent",
                },
                traceparent=carrier.get("traceparent"),
                tracestate=carrier.get("tracestate", ""),
            )
        )
    except (ConnectionError, asyncio.TimeoutError) as exc:
        logger.error("Network error in PoliciesAgent: %s", exc, exc_info=True)
        carrier = {}
        TraceContextTextMapPropagator().inject(carrier)
        await human_channel.publish(
            TracedMessage(
                type="agent_message",
                source="PoliciesAgent",
                data={
                    "message": "I'm having network issues processing your request. Please try again.",
                    "connection_id": connection_id,
                    "agent": "PoliciesAgent",
                },
                traceparent=carrier.get("traceparent"),
                tracestate=carrier.get("tracestate", ""),
            )
        )
    except Exception as exc:
        logger.error(f"Unhandled error in PoliciesAgent: {exc}", exc_info=True)
        carrier = {}
        TraceContextTextMapPropagator().inject(carrier)
        await human_channel.publish(
            TracedMessage(
                type="agent_message",
                source="PoliciesAgent",
                data={
                    "message": "I apologize, but I'm having trouble processing your request right now. Please try again.",
                    "connection_id": connection_id,
                    "agent": "PoliciesAgent",
                },
                traceparent=carrier.get("traceparent"),
                tracestate=carrier.get("tracestate", ""),
            )
        )


@policies_agent.subscribe(channel=agents_channel)
async def handle_other_messages(msg: TracedMessage) -> None:
    """Handle non-policy messages received on the agent channel."""
    logger.debug("Received non-policy message: %s", msg)


