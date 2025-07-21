import importlib
from typing import Any, Callable, Dict, List

import dspy.streaming
from eggai import Agent, Channel
from opentelemetry import trace

from agents.triage.config import GROUP_ID, settings
from agents.triage.dspy_modules.small_talk import chatty
from agents.triage.models import AGENT_REGISTRY, TargetAgent
from libraries.communication.channels import channels
from libraries.communication.messaging import MessageType, OffsetReset, subscribe
from libraries.observability.logger import get_console_logger
from libraries.observability.tracing import (
    TracedMessage,
    format_span_as_traceparent,
    traced_handler,
)
from libraries.observability.tracing.otel import safe_set_attribute

_CLASSIFIER_PATHS = {
    "v0": ("agents.triage.dspy_modules.classifier_v0", "classifier_v0"),
    "v1": ("agents.triage.dspy_modules.classifier_v1", "classifier_v1"),
    "v2": ("agents.triage.dspy_modules.classifier_v2.classifier_v2", "classifier_v2"),
    "v3": ("agents.triage.baseline_model.classifier_v3", "classifier_v3"),
    "v4": ("agents.triage.dspy_modules.classifier_v4", "classifier_v4"),
    "v5": ("agents.triage.attention_net.classifier_v5", "classifier_v5"),
    "v6": ("agents.triage.classifier_v6.classifier_v6", "classifier_v6"),
    "v7": ("agents.triage.classifier_v7.classifier_v7", "classifier_v7"),
}

def build_conversation_string(chat_messages: List[Dict[str, str]]) -> str:
    """Build a conversation history string from a list of chat entries."""
    lines: List[str] = []
    for chat in chat_messages:
        user = chat.get("agent", "User")
        content = chat.get("content", "")
        if content:
            lines.append(f"{user}: {content}")
    return "\n".join(lines) + ("\n" if lines else "")

async def _publish_to_agent(
    conversation_string: str, target_agent: TargetAgent, msg: TracedMessage
) -> None:
    """Publish a single classified user message to a specialized agent."""
    logger.info(f"Routing message to {target_agent}")
    with tracer.start_as_current_span("publish_to_agent") as span:
        safe_set_attribute(span, "target_agent", str(target_agent))
        safe_set_attribute(span, "conversation_length", len(conversation_string))
        child_traceparent, child_tracestate = format_span_as_traceparent(span)
        triage_to_agent_messages = [
            {
                "role": "user",
                "content": f"{conversation_string} \n{target_agent}: ",
            }
        ]
        await agents_channel.publish(
            TracedMessage(
                type=AGENT_REGISTRY[target_agent]["message_type"],
                source="Triage",
                data={
                    "chat_messages": triage_to_agent_messages,
                    "message_id": msg.id,
                    "connection_id": msg.data.get("connection_id", "unknown"),
                },
                traceparent=child_traceparent,
                tracestate=child_tracestate,
            )
        )

async def _stream_chatty_response(
    conversation_string: str, msg: TracedMessage
) -> None:
    """Stream a 'chatty' (small-talk) response back to the human stream channel."""
    with tracer.start_as_current_span("chatty_stream_response") as span:
        safe_set_attribute(span, "conversation_length", len(conversation_string))
        child_traceparent, child_tracestate = format_span_as_traceparent(span)
        stream_message_id = str(msg.id)

        await human_stream_channel.publish(
            TracedMessage(
                type="agent_message_stream_start",
                source="Triage",
                data={
                    "message_id": stream_message_id,
                    "connection_id": msg.data.get("connection_id", "unknown"),
                },
                traceparent=child_traceparent,
                tracestate=child_tracestate,
            )
        )

        chunks = chatty(chat_history=conversation_string)
        chunk_count = 0

        async for chunk in chunks:
            if isinstance(chunk, dspy.streaming.StreamResponse):
                chunk_count += 1
                await human_stream_channel.publish(
                    TracedMessage(
                        type="agent_message_stream_chunk",
                        source="Triage",
                        data={
                            "message_chunk": chunk.chunk,
                            "message_id": stream_message_id,
                            "chunk_index": chunk_count,
                            "connection_id": msg.data.get("connection_id", "unknown"),
                        },
                        traceparent=child_traceparent,
                        tracestate=child_tracestate,
                    )
                )
                logger.info(f"Chunk {chunk_count} sent: {chunk.chunk}")
            elif isinstance(chunk, dspy.Prediction):
                chunk.response = chunk.response.replace(" [[ ## completed ## ]]", "")

                await human_stream_channel.publish(
                    TracedMessage(
                        type="agent_message_stream_end",
                        source="Triage",
                        data={
                            "message_id": stream_message_id,
                            "agent": "Triage",
                            "connection_id": msg.data.get("connection_id", "unknown"),
                            "message": chunk.response,
                        },
                        traceparent=child_traceparent,
                        tracestate=child_tracestate,
                    )
                )
triage_agent = Agent(name="Triage")
human_channel = Channel(channels.human)
human_stream_channel = Channel(channels.human_stream)
agents_channel = Channel(channels.agents)

tracer = trace.get_tracer("triage_agent")
logger = get_console_logger("triage_agent.handler")


def get_current_classifier() -> Callable[..., Any]:
    """Lazily import and return the classifier function based on the configured version."""
    try:
        module_path, fn_name = _CLASSIFIER_PATHS[settings.classifier_version]
    except KeyError:
        raise ValueError(f"Unknown classifier version: {settings.classifier_version}")
    module = importlib.import_module(module_path)
    return getattr(module, fn_name)


current_classifier = get_current_classifier()


@subscribe(
    agent=triage_agent,
    channel=human_channel,
    message_type=MessageType.USER_MESSAGE,
    group_id=GROUP_ID,
    auto_offset_reset=OffsetReset.LATEST,
)
@traced_handler("handle_user_message")
async def handle_user_message(msg: TracedMessage) -> None:
    """Main handler for user messages: classify and route or stream chatty responses."""
    chat_messages: List[Dict[str, Any]] = msg.data.get("chat_messages", [])
    connection_id: str = msg.data.get("connection_id", "unknown")

    span = trace.get_current_span()
    safe_set_attribute(span, "connection_id", connection_id)
    safe_set_attribute(span, "num_chat_messages", len(chat_messages))

    logger.info(f"Received message from connection {connection_id}")
    if not chat_messages:
        safe_set_attribute(span, "empty_chat_history", True)
        logger.warning("Empty chat history for connection %s", connection_id)
        await human_channel.publish(
            TracedMessage(
                type="agent_message",
                source="Triage",
                data={
                    "message": "Sorry, I didn't receive any message to process.",
                    "connection_id": connection_id,
                    "agent": "TriageAgent",
                },
            )
        )
        return

    conversation_string = build_conversation_string(chat_messages)
    safe_set_attribute(span, "conversation_length", len(conversation_string))

    try:
        response = current_classifier(chat_history=conversation_string)
        safe_set_attribute(span, "classifier_version", settings.classifier_version)
        safe_set_attribute(span, "target_agent", str(response.target_agent))
        safe_set_attribute(span, "classification_latency_ms", response.metrics.latency_ms)
    except ValueError as e:
        safe_set_attribute(span, "error", str(e))
        logger.error("Classifier configuration error: %s", e)
        await human_channel.publish(
            TracedMessage(
                type="agent_message",
                source="Triage",
                data={
                    "message": f"Configuration error: {e}",
                    "connection_id": connection_id,
                    "agent": "TriageAgent",
                },
            )
        )
        return
    except Exception as e:
        safe_set_attribute(span, "error", "classification_failure")
        logger.error("Error during classification: %s", e, exc_info=True)
        await human_channel.publish(
            TracedMessage(
                type="agent_message",
                source="Triage",
                data={
                    "message": "Sorry, I encountered an error while classifying your message.",
                    "connection_id": connection_id,
                    "agent": "TriageAgent",
                },
            )
        )
        return

    target_agent = response.target_agent
    logger.info(
        f"Classification completed in {response.metrics.latency_ms:.2f} ms, "
        f"target agent: {target_agent}, classifier: {settings.classifier_version}"
    )

    if target_agent != TargetAgent.ChattyAgent:
        try:
            await _publish_to_agent(conversation_string, target_agent, msg)
        except Exception as e:
            logger.error("Error routing to agent %s: %s", target_agent, e, exc_info=True)
            await human_channel.publish(
                TracedMessage(
                    type="agent_message",
                    source="Triage",
                    data={
                        "message": "Sorry, I couldn't route your request due to an internal error.",
                        "connection_id": connection_id,
                        "agent": "TriageAgent",
                    },
                )
            )
    else:
        try:
            await _stream_chatty_response(conversation_string, msg)
        except Exception as e:
            logger.error("Error streaming chatty response: %s", e, exc_info=True)
            await human_stream_channel.publish(
                TracedMessage(
                    type="agent_message_stream_end",
                    source="Triage",
                    data={
                        "message_id": str(msg.id),
                        "connection_id": connection_id,
                        "agent": "TriageAgent",
                        "message": "Sorry, I encountered an error generating a response.",
                    },
                )
            )


@triage_agent.subscribe(channel=human_channel)
async def handle_others(msg: TracedMessage) -> None:
    """Fallback handler for other message types on the human channel."""
    logger.debug("Received message: %s", msg)


