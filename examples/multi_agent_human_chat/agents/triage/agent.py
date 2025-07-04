"""Triage agent handler: classify user messages and route or stream responses."""
import dspy.streaming
from eggai import Agent, Channel
from opentelemetry import trace

from agents.triage.config import settings
from agents.triage.dspy_modules.small_talk import chatty
from agents.triage.models import AGENT_REGISTRY, TargetAgent
import importlib
from typing import Callable, Any, List, Dict
from libraries.channels import channels
from libraries.logger import get_console_logger
from libraries.tracing import TracedMessage, format_span_as_traceparent, traced_handler

# Lazy-loaded classifier registry: maps version to (module path, function name)
_CLASSIFIER_PATHS = {
    "v0": ("agents.triage.dspy_modules.classifier_v0", "classifier_v0"),
    "v1": ("agents.triage.dspy_modules.classifier_v1", "classifier_v1"),
    "v2": ("agents.triage.dspy_modules.classifier_v2.classifier_v2", "classifier_v2"),
    "v3": ("agents.triage.baseline_model.classifier_v3", "classifier_v3"),
    "v4": ("agents.triage.dspy_modules.classifier_v4", "classifier_v4"),
    "v5": ("agents.triage.attention_net.classifier_v5", "classifier_v5"),
}

async def _publish_to_agent(
    conversation_string: str, target_agent: TargetAgent, msg: TracedMessage
) -> None:
    """
    Publish a single classified user message to a specialized agent.

    Starts a tracing span and sends the routed message over the agents_channel transport.
    """
    logger.info(f"Routing message to {target_agent}")
    with tracer.start_as_current_span("publish_to_agent") as span:
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
                source="TriageAgent",
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
    """
    Stream a 'chatty' (small-talk) response back to the human stream channel.

    Sends a start event, emits each chunk, and a final end event, with tracing.
    """
    with tracer.start_as_current_span("chatty_stream_response") as span:
        child_traceparent, child_tracestate = format_span_as_traceparent(span)
        stream_message_id = str(msg.id)

        await human_stream_channel.publish(
            TracedMessage(
                type="agent_message_stream_start",
                source="TriageAgent",
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
                        source="TriageAgent",
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
                # FIXME: with short prompts, dspy sometimes leaves the suffix untrimmed
                chunk.response = chunk.response.replace(" [[ ## completed ## ]]", "")

                await human_stream_channel.publish(
                    TracedMessage(
                        type="agent_message_stream_end",
                        source="TriageAgent",
                        data={
                            "message_id": stream_message_id,
                            "agent": "TriageAgent",
                            "connection_id": msg.data.get("connection_id", "unknown"),
                            "message": chunk.response,
                        },
                        traceparent=child_traceparent,
                        tracestate=child_tracestate,
                    )
                )
                logger.info(


triage_agent = Agent(name="TriageAgent")
human_channel = Channel(channels.human)
human_stream_channel = Channel(channels.human_stream)
agents_channel = Channel(channels.agents)

tracer = trace.get_tracer("triage_agent")
logger = get_console_logger("triage_agent.handler")


def get_current_classifier() -> Callable[..., Any]:
    """
    Lazily import and return the classifier function based on the configured version.

    Raises:
        ValueError: If the configured classifier_version is not supported.
    """
    try:
        module_path, fn_name = _CLASSIFIER_PATHS[settings.classifier_version]
    except KeyError:
        raise ValueError(f"Unknown classifier version: {settings.classifier_version}")
    module = importlib.import_module(module_path)
    return getattr(module, fn_name)


current_classifier = get_current_classifier()


@triage_agent.subscribe(
    channel=human_channel,
    filter_by_message=lambda msg: msg.get("type") == "user_message",
    auto_offset_reset="latest",
    group_id="triage_agent_group",
)
@traced_handler("handle_user_message")
async def handle_user_message(msg: TracedMessage) -> None:
    """
    Handle incoming user messages: classify and route or stream chatty responses.

    Extracts the chat history, invokes the current classifier, and delegates to
    publishing or streaming helpers based on the target agent.
    """
    try:
        chat_messages = msg.data.get("chat_messages", [])
        connection_id = msg.data.get("connection_id", "unknown")

        logger.info(f"Received message from connection {connection_id}")
        conversation_string = build_conversation_string(chat_messages)

        response = current_classifier(chat_history=conversation_string)
        target_agent = response.target_agent

        logger.info(
            f"Classification completed in {response.metrics.latency_ms:.2f} ms, target agent: {target_agent}, classifier version: {settings.classifier_version}"
        )
        if target_agent != TargetAgent.ChattyAgent:
            await _publish_to_agent(conversation_string, target_agent, msg)
        else:
            await _stream_chatty_response(conversation_string, msg)

    except Exception as e:
        logger.error(f"Error processing message: {e}", exc_info=True)


@triage_agent.subscribe(channel=human_channel)
async def handle_others(msg: TracedMessage) -> None:
    """
    Fallback handler for other message types on the human channel.

    Logs events at debug level; no routing or response is performed.
    """
    logger.debug("Received message: %s", msg)


