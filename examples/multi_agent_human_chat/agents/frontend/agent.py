import asyncio
import os
import uuid

import uvicorn
from eggai import Agent, Channel
from fastapi import FastAPI, Query
from opentelemetry import trace
from starlette.websockets import WebSocket, WebSocketDisconnect

from libraries.logger import get_console_logger
from libraries.tracing import TracedMessage
from libraries.tracing.init_metrics import init_token_metrics
from libraries.tracing.otel import (
    extract_span_context,
    safe_set_attribute,
    traced_handler,
)

from .config import settings
from .types import MessageType
from .websocket_manager import WebSocketManager

logger = get_console_logger("frontend_agent")

GUARDRAILS_ENABLED = os.getenv("GUARDRAILS_TOKEN") is not None

if GUARDRAILS_ENABLED:
    try:
        from .guardrails import toxic_language_guard
    except ImportError as e:
        logger.error(f"Failed to import guardrails: {e}")
        toxic_language_guard = None
else:
    logger.info("Guardrails disabled (no GUARDRAILS_TOKEN)")
    toxic_language_guard = None


frontend_agent = Agent("FrontendAgent")
human_channel = Channel("human")
human_stream_channel = Channel("human_stream")
websocket_manager = WebSocketManager()
tracer = trace.get_tracer("frontend_agent")
init_token_metrics(
    port=settings.prometheus_metrics_port, application_name=settings.app_name
)

def _extract_trace_context(connection_id: str) -> tuple[str, str, trace.SpanContext]:
    with tracer.start_as_current_span("frontend_chat", context=None) as root_span:
        root_ctx = root_span.get_span_context()
        traceparent = (
            f"00-{root_ctx.trace_id:032x}-{root_ctx.span_id:016x}-{root_ctx.trace_flags:02x}"
        )
        safe_set_attribute(root_span, "connection.id", str(connection_id))
        tracestate = str(root_ctx.trace_state) if root_ctx.trace_state else ""
    ctx = extract_span_context(traceparent, tracestate)
    parent_ctx = trace.set_span_in_context(trace.NonRecordingSpan(ctx))
    return traceparent, tracestate, parent_ctx


async def _initialize_connection(websocket: WebSocket, connection_id: str) -> None:
    await websocket_manager.connect(websocket, connection_id)
    await websocket_manager.send_message_to_connection(
        connection_id, {"connection_id": connection_id}
    )


async def _process_user_messages(
    server: uvicorn.Server,
    websocket: WebSocket,
    connection_id: str,
    traceparent: str,
    tracestate: str,
) -> None:
    while True:
        try:
            data = await asyncio.wait_for(websocket.receive_json(), timeout=1)
        except asyncio.TimeoutError:
            if server.should_exit:
                await websocket_manager.disconnect(connection_id)
                for conn in server.server_state.connections or []:
                    if hasattr(conn, "shutdown"):
                        conn.shutdown()
                break
            continue

        message_id = str(uuid.uuid4())
        content = data.get("payload")

        if GUARDRAILS_ENABLED and toxic_language_guard:
            valid = await toxic_language_guard(content)
            if valid is None:
                await human_channel.publish(
                    TracedMessage(
                        id=message_id,
                        source="FrontendAgent",
                        type=MessageType.AGENT_MESSAGE.value,
                        data={
                            "message": "Sorry, I can't help you with that.",
                            "connection_id": connection_id,
                            "agent": "TriageAgent",
                        },
                        traceparent=traceparent,
                        tracestate=tracestate,
                    )
                )
                continue
        else:
            valid = content

        await websocket_manager.attach_message_id(message_id, connection_id)
        websocket_manager.chat_messages[connection_id].append(
            {"role": "user", "content": valid, "id": message_id, "agent": "User"}
        )
        await human_channel.publish(
            TracedMessage(
                id=message_id,
                source="FrontendAgent",
                type=MessageType.USER_MESSAGE.value,
                data={
                    "chat_messages": websocket_manager.chat_messages[connection_id],
                    "connection_id": connection_id,
                },
                traceparent=traceparent,
                tracestate=tracestate,
            )
        )


@tracer.start_as_current_span("add_websocket_gateway")
def add_websocket_gateway(route: str, app: FastAPI, server: uvicorn.Server) -> None:
    @app.websocket(route)
    async def websocket_handler(
        websocket: WebSocket, connection_id: str = Query(None, alias="connection_id")
    ):
        if server.should_exit:
            websocket.state.closed = True
            return

        if connection_id is None:
            connection_id = str(uuid.uuid4())

        traceparent, tracestate, parent_ctx = _extract_trace_context(connection_id)

        with tracer.start_as_current_span(
            "websocket_connection", context=parent_ctx, kind=trace.SpanKind.SERVER
        ) as span:
            try:
                safe_set_attribute(span, "connection.id", str(connection_id))
                await _initialize_connection(websocket, connection_id)
                await _process_user_messages(
                    server, websocket, connection_id, traceparent, tracestate
                )
            except WebSocketDisconnect:
                logger.info(f"WebSocket disconnected: {connection_id}")
            except Exception as e:
                logger.error(
                    f"Error with WebSocket {connection_id}: {e}", exc_info=True
                )
            finally:
                await websocket_manager.disconnect(connection_id)
                logger.info(f"WebSocket connection {connection_id} closed.")


@frontend_agent.subscribe(channel=human_stream_channel)
async def handle_human_stream_messages(message: TracedMessage):
    message_type = message.type
    agent = message.source
    message_id = message.data.get("message_id")
    connection_id = message.data.get("connection_id")

    if message_type == MessageType.AGENT_MESSAGE_STREAM_START.value:
        logger.info(f"Starting stream for message {message_id} from {agent}")
        await websocket_manager.send_message_to_connection(
            connection_id,
            {
                "sender": agent,
                "content": "",
                "type": MessageType.ASSISTANT_MESSAGE_STREAM_START.value,
            },
        )

    elif message_type == MessageType.AGENT_MESSAGE_STREAM_WAITING_MESSAGE.value:
        message = message.data.get("message")
        await websocket_manager.send_message_to_connection(
            connection_id,
            {
                "sender": agent,
                "content": message,
                "type": MessageType.ASSISTANT_MESSAGE_STREAM_WAITING_MESSAGE.value,
            },
        )

    elif message_type == MessageType.AGENT_MESSAGE_STREAM_CHUNK.value:
        chunk = message.data.get("message_chunk", "")
        chunk_index = message.data.get("chunk_index")
        await websocket_manager.send_message_to_connection(
            connection_id,
            {
                "sender": agent,
                "content": chunk,
                "chunk_index": chunk_index,
                "type": MessageType.ASSISTANT_MESSAGE_STREAM_CHUNK.value,
            },
        )
    elif message_type == MessageType.AGENT_MESSAGE_STREAM_END.value:
        final_content = message.data.get("message", "")
        websocket_manager.chat_messages[connection_id].append(
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
                "type": MessageType.ASSISTANT_MESSAGE_STREAM_END.value,
            },
        )


@frontend_agent.subscribe(channel=human_channel)
@traced_handler("handle_human_messages")
async def handle_human_messages(message: TracedMessage):
    message_type = message.type
    agent = message.data.get("agent")
    connection_id = message.data.get("connection_id")
    message_id = message.id

    if message_type == "agent_message":
        content = message.data.get("message")
        websocket_manager.chat_messages[connection_id].append(
            {
                "role": "assistant",
                "content": content,
                "agent": agent,
                "id": message_id,
            }
        )

        await websocket_manager.send_message_to_connection(
            connection_id,
            {"sender": agent, "content": content, "type": MessageType.ASSISTANT_MESSAGE.value},
        )
