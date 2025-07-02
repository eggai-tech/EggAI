"""Shared helpers for streaming agent responses."""

from __future__ import annotations

from typing import AsyncIterable, Dict, List, Union

from dspy import Prediction
from dspy.streaming import StreamResponse
from eggai import Channel

from libraries.logger import get_console_logger
from libraries.tracing import TracedMessage
from libraries.tracing.otel import safe_set_attribute


async def process_request_stream(
    model_iterator: AsyncIterable[Union[StreamResponse, Prediction]],
    *,
    agent_name: str,
    connection_id: str,
    message_id: str,
    human_stream_channel: Channel,
    tracer,
    logger=None,
    child_traceparent: str,
    child_tracestate: str,
) -> None:
    """Publish streaming chunks for an agent response."""
    if logger is None:
        logger = get_console_logger(f"{agent_name.lower()}.stream")

    await human_stream_channel.publish(
        TracedMessage(
            type="agent_message_stream_start",
            source=agent_name,
            data={"message_id": message_id, "connection_id": connection_id},
            traceparent=child_traceparent,
            tracestate=child_tracestate,
        )
    )
    logger.info(f"Stream started for message {message_id}")

    chunk_count = 0
    try:
        async for chunk in model_iterator:
            if isinstance(chunk, StreamResponse):
                chunk_count += 1
                try:
                    await human_stream_channel.publish(
                        TracedMessage(
                            type="agent_message_stream_chunk",
                            source=agent_name,
                            data={
                                "message_chunk": chunk.chunk,
                                "message_id": message_id,
                                "chunk_index": chunk_count,
                                "connection_id": connection_id,
                            },
                            traceparent=child_traceparent,
                            tracestate=child_tracestate,
                        )
                    )
                except ConnectionError as pub_exc:
                    if logger:
                        logger.error(
                            f"Connection error publishing stream chunk: {pub_exc}",
                            exc_info=True,
                        )
                    raise
            elif isinstance(chunk, Prediction):
                response = chunk.final_response
                if response:
                    response = response.replace(" [[ ## completed ## ]]", "")
                try:
                    await human_stream_channel.publish(
                        TracedMessage(
                            type="agent_message_stream_end",
                            source=agent_name,
                            data={
                                "message_id": message_id,
                                "message": response,
                                "agent": agent_name,
                                "connection_id": connection_id,
                            },
                            traceparent=child_traceparent,
                            tracestate=child_tracestate,
                        )
                    )
                    logger.info(f"Stream ended for message {message_id}")
                except ConnectionError as pub_exc:
                    if logger:
                        logger.error(
                            f"Connection error sending final chunk: {pub_exc}",
                            exc_info=True,
                        )
                    raise
    except Exception as exc:  # noqa: BLE001
        if logger:
            logger.error(f"Error in streaming response: {exc}", exc_info=True)
        await human_stream_channel.publish(
            TracedMessage(
                type="agent_message_stream_end",
                source=agent_name,
                data={
                    "message_id": message_id,
                    "message": "I'm sorry, I encountered an error while processing your request.",
                    "agent": agent_name,
                    "connection_id": connection_id,
                },
                traceparent=child_traceparent,
                tracestate=child_tracestate,
            )
        )


def format_conversation(
    chat_messages: List[Dict[str, str]],
    *,
    tracer,
    logger=None,
) -> str:
    """Combine chat messages into a conversation string."""
    if logger is None:
        logger = get_console_logger("streaming_agent.conversation")

    with tracer.start_as_current_span("get_conversation_string") as span:
        safe_set_attribute(span, "chat_messages_count", len(chat_messages) if chat_messages else 0)

        if not chat_messages:
            safe_set_attribute(span, "empty_messages", True)
            return ""

        conversation_parts: List[str] = []
        for chat in chat_messages:
            if "content" not in chat:
                safe_set_attribute(span, "invalid_message", True)
                if logger:
                    logger.warning("Message missing content field")
                continue

            role = chat.get("role", "User")
            conversation_parts.append(f"{role}: {chat['content']}")

        conversation = "\n".join(conversation_parts) + "\n"
        safe_set_attribute(span, "conversation_length", len(conversation))
        return conversation
