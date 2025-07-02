from __future__ import annotations

from libraries.tracing import TracedMessage
from libraries.tracing.otel import traced_handler

from .agent import (
    frontend_agent,
    human_channel,
    human_stream_channel,
    logger,
    messages_cache,
    websocket_manager,
)


@frontend_agent.subscribe(channel=human_stream_channel)
async def handle_human_stream_messages(message: TracedMessage) -> None:
    """Forward streamed agent responses to the connected websocket."""
    message_type = message.type
    agent = message.source
    message_id = message.data.get("message_id")
    connection_id = message.data.get("connection_id")

    if message_type == "agent_message_stream_start":
        logger.info("Starting stream for message %s from %s", message_id, agent)
        await websocket_manager.send_message_to_connection(
            connection_id,
            {"sender": agent, "content": "", "type": "assistant_message_stream_start"},
        )

    elif message_type == "agent_message_stream_waiting_message":
        waiting_msg = message.data.get("message")
        await websocket_manager.send_message_to_connection(
            connection_id,
            {
                "sender": agent,
                "content": waiting_msg,
                "type": "assistant_message_stream_waiting_message",
            },
        )

    elif message_type == "agent_message_stream_chunk":
        chunk = message.data.get("message_chunk", "")
        chunk_index = message.data.get("chunk_index")
        await websocket_manager.send_message_to_connection(
            connection_id,
            {
                "sender": agent,
                "content": chunk,
                "chunk_index": chunk_index,
                "type": "assistant_message_stream_chunk",
            },
        )
    elif message_type == "agent_message_stream_end":
        final_content = message.data.get("message", "")
        messages_cache[connection_id].append(
            {
                "role": "assistant",
                "content": final_content,
                "agent": agent,
                "id": str(message_id),
            }
        )
        await websocket_manager.send_message_to_connection(
            connection_id,
            {
                "sender": agent,
                "content": final_content,
                "type": "assistant_message_stream_end",
            },
        )


@frontend_agent.subscribe(channel=human_channel)
@traced_handler("handle_human_messages")
async def handle_human_messages(message: TracedMessage) -> None:
    """Handle completed agent responses and user messages."""
    message_type = message.type
    agent = message.data.get("agent")
    connection_id = message.data.get("connection_id")
    message_id = message.id

    if connection_id not in messages_cache:
        messages_cache[connection_id] = []

    if message_type == "agent_message":
        content = message.data.get("message")
        messages_cache[connection_id].append(
            {
                "role": "assistant",
                "content": content,
                "agent": agent,
                "id": message_id,
            }
        )

        await websocket_manager.send_message_to_connection(
            connection_id,
            {"sender": agent, "content": content, "type": "assistant_message"},
        )
