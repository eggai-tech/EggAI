import asyncio
from typing import List

from eggai import Agent, Channel
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

from agents.claims.config import settings
from agents.claims.dspy_modules.claims import claims_optimized_dspy
from agents.claims.types import ChatMessage, ModelConfig
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

claims_agent = Agent(name="ClaimsAgent")
logger = get_console_logger("claims_agent.handler")
agents_channel = Channel(channels.agents)
human_channel = Channel(channels.human)
human_stream_channel = Channel(channels.human_stream)
tracer = get_tracer("claims_agent")

init_token_metrics(
    port=settings.prometheus_metrics_port, application_name=settings.app_name
)


def get_conversation_string(chat_messages: List[ChatMessage]) -> str:
    """Legacy wrapper for tests that formats chat history."""
    return format_conversation(chat_messages, tracer=tracer, logger=logger)


async def process_claims_request(
    conversation_string: str,
    connection_id: str,
    message_id: str,
    timeout_seconds: float | None = None,
) -> None:
    """Stream a claims response back to the user.

    Args:
        conversation_string: Formatted conversation history.
        connection_id: Identifier of the user's connection.
        message_id: Unique ID for this claims request.
        timeout_seconds: Optional model timeout override.

    Returns:
        None
    """
    # Create model config with timeout value
    config = ModelConfig(
        name="claims_react",
        timeout_seconds=timeout_seconds or settings.request_timeout_seconds,
    )
    with tracer.start_as_current_span("process_claims_request") as span:
        carrier = {}
        TraceContextTextMapPropagator().inject(carrier)
        child_traceparent = carrier.get("traceparent")
        child_tracestate = carrier.get("tracestate", "")
        safe_set_attribute(span, "connection_id", connection_id)
        safe_set_attribute(span, "message_id", message_id)
        safe_set_attribute(span, "conversation_length", len(conversation_string))
        safe_set_attribute(span, "timeout_seconds", config.timeout_seconds)

        if not conversation_string or len(conversation_string.strip()) < 5:
            safe_set_attribute(span, "error", "Empty or too short conversation")
            span.set_status(1, "Invalid input")
            raise ValueError("Conversation history is too short to process")

        logger.info("Calling claims model with streaming")
        chunks = claims_optimized_dspy(chat_history=conversation_string, config=config)

        await process_request_stream(
            chunks,
            agent_name="ClaimsAgent",
            connection_id=connection_id,
            message_id=message_id,
            human_stream_channel=human_stream_channel,
            tracer=tracer,
            logger=logger,
            child_traceparent=child_traceparent,
            child_tracestate=child_tracestate,
        )


@claims_agent.subscribe(
    channel=agents_channel,
    filter_by_message=lambda msg: msg.get("type") == "claim_request",
    auto_offset_reset="latest",
    group_id="claims_agent_group",
)
@traced_handler("handle_claim_request")
async def handle_claim_request(msg: TracedMessage) -> None:
    """Process a claim request from the agents channel.

    Args:
        msg: The traced message containing chat history and metadata.

    Returns:
        None
    """
    try:
        chat_messages: List[ChatMessage] = msg.data.get("chat_messages", [])
        connection_id: str = msg.data.get("connection_id", "unknown")

        if not chat_messages:
            logger.warning(f"Empty chat history for connection: {connection_id}")
            carrier = {}
            TraceContextTextMapPropagator().inject(carrier)
            await human_channel.publish(
                TracedMessage(
                    type="agent_message",
                    source="ClaimsAgent",
                    data={
                        "message": "I apologize, but I didn't receive any message content to process.",
                        "connection_id": connection_id,
                        "agent": "ClaimsAgent",
                    },
                    traceparent=carrier.get("traceparent"),
                    tracestate=carrier.get("tracestate", ""),
                )
            )
            return

        conversation_string = format_conversation(
            chat_messages, tracer=tracer, logger=logger
        )
        logger.info(f"Processing claim request for connection {connection_id}")

        await process_claims_request(
            conversation_string,
            connection_id,
            str(msg.id),
            timeout_seconds=settings.request_timeout_seconds,
        )

    except ValueError as exc:
        logger.warning("Invalid claims request: %s", exc, exc_info=True)
        carrier = {}
        TraceContextTextMapPropagator().inject(carrier)
        await human_channel.publish(
            TracedMessage(
                type="agent_message",
                source="ClaimsAgent",
                data={
                    "message": str(exc),
                    "connection_id": connection_id,
                    "agent": "ClaimsAgent",
                },
                traceparent=carrier.get("traceparent"),
                tracestate=carrier.get("tracestate", ""),
            )
        )
    except (ConnectionError, asyncio.TimeoutError) as exc:
        logger.error("Network error in ClaimsAgent: %s", exc, exc_info=True)
        carrier = {}
        TraceContextTextMapPropagator().inject(carrier)
        await human_channel.publish(
            TracedMessage(
                type="agent_message",
                source="ClaimsAgent",
                data={
                    "message": "I'm having network issues processing your request. Please try again.",
                    "connection_id": connection_id,
                    "agent": "ClaimsAgent",
                },
                traceparent=carrier.get("traceparent"),
                tracestate=carrier.get("tracestate", ""),
            )
        )
    except Exception as exc:
        logger.error(f"Unhandled error in ClaimsAgent: {exc}", exc_info=True)
        carrier = {}
        TraceContextTextMapPropagator().inject(carrier)
        await human_channel.publish(
            TracedMessage(
                type="agent_message",
                source="ClaimsAgent",
                data={
                    "message": "I apologize, but I'm having trouble processing your request right now. Please try again.",
                    "connection_id": connection_id,
                    "agent": "ClaimsAgent",
                },
                traceparent=carrier.get("traceparent"),
                tracestate=carrier.get("tracestate", ""),
            )
        )


@claims_agent.subscribe(channel=agents_channel)
async def handle_other_messages(msg: TracedMessage) -> None:
    """Handle non-claim messages received on the agent channel.

    Args:
        msg: Incoming message that does not match this agent's filter.

    Returns:
        None
    """
    logger.debug("Received non-claim message: %s", msg)


