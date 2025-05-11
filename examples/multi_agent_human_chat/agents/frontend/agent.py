import asyncio
import os
import uuid

import uvicorn
from eggai import Agent, Channel
from eggai.transport import eggai_set_default_transport
from fastapi import FastAPI, Query
from opentelemetry import trace
from starlette.websockets import WebSocket, WebSocketDisconnect

from libraries.kafka_transport import create_kafka_transport
from libraries.logger import get_console_logger
from libraries.tracing import TracedMessage
from libraries.tracing.otel import (
    extract_span_context,
    safe_set_attribute,
    traced_handler,
)

from .config import settings
from .websocket_manager import WebSocketManager

logger = get_console_logger("frontend_agent")

# Load environment variable
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

# Set up Kafka transport
eggai_set_default_transport(
    lambda: create_kafka_transport(
        bootstrap_servers=settings.kafka_bootstrap_servers,
        ssl_cert=settings.kafka_ca_content
    )
)

frontend_agent = Agent("FrontendAgent")
human_channel = Channel("human")
websocket_manager = WebSocketManager()
messages_cache = {}
tracer = trace.get_tracer("frontend_agent")


@tracer.start_as_current_span("add_websocket_gateway")
def add_websocket_gateway(route: str, app: FastAPI, server: uvicorn.Server):
    @app.websocket(route)
    async def websocket_handler(
            websocket: WebSocket, 
            connection_id: str = Query(None, alias="connection_id")
    ):
        if server.should_exit:
            websocket.state.closed = True
            return
            
        if connection_id is None:
            connection_id = str(uuid.uuid4())

        if connection_id not in messages_cache:
            messages_cache[connection_id] = []

        # Create root span for the connection
        with tracer.start_as_current_span("frontend_chat", context=None) as root_span:
            root_span_ctx = root_span.get_span_context()
            trace_parent = (
                f"00-{root_span_ctx.trace_id:032x}-"
                f"{root_span_ctx.span_id:016x}-"
                f"{root_span_ctx.trace_flags:02x}"
            )
            safe_set_attribute(root_span, 'connection.id', str(connection_id))
            trace_state = str(root_span_ctx.trace_state) if root_span_ctx.trace_state else ""

        # Extract span context for child spans
        root_span_ctx = extract_span_context(trace_parent, trace_state)
        parent_context = trace.set_span_in_context(trace.NonRecordingSpan(root_span_ctx))
        
        with tracer.start_as_current_span(
                "websocket_connection",
                context=parent_context,
                kind=trace.SpanKind.SERVER
        ) as span:
            try:
                safe_set_attribute(span, 'connection.id', str(connection_id))
                await websocket_manager.connect(websocket, connection_id)
                await websocket_manager.send_message_to_connection(
                    connection_id, {"connection_id": connection_id}
                )
                
                while True:
                    try:
                        data = await asyncio.wait_for(websocket.receive_json(), timeout=1)
                    except asyncio.TimeoutError:
                        if server.should_exit:
                            await websocket_manager.disconnect(connection_id)
                            # Close all connections when server is shutting down
                            conns = server.server_state.connections or []
                            for conn in conns:
                                if "shutdown" in dir(conn):
                                    conn.shutdown()
                            break
                        continue
                        
                    message_id = str(uuid.uuid4())
                    content = data.get("payload")

                    # Apply content moderation if enabled
                    if GUARDRAILS_ENABLED and toxic_language_guard:
                        valid_content = await toxic_language_guard(content)
                        if valid_content is None:
                            await human_channel.publish(
                                TracedMessage(
                                    id=message_id,
                                    source="FrontendAgent",
                                    type="agent_message",
                                    data={
                                        "message": "Sorry, I can't help you with that.",
                                        "connection_id": connection_id,
                                        "agent": "TriageAgent",
                                    },
                                    traceparent=trace_parent,
                                    tracestate=trace_state,
                                )
                            )
                            continue
                    else:
                        valid_content = content

                    await websocket_manager.attach_message_id(message_id, connection_id)
                    messages_cache[connection_id].append(
                        {
                            "role": "user",
                            "content": valid_content,
                            "id": message_id,
                            "agent": "User",
                        }
                    )
                    
                    await human_channel.publish(
                        TracedMessage(
                            id=message_id,
                            source="FrontendAgent",
                            type="user_message",
                            data={
                                "chat_messages": messages_cache[connection_id],
                                "connection_id": connection_id,
                            },
                            traceparent=trace_parent,
                            tracestate=trace_state,
                        )
                    )
                    
            except WebSocketDisconnect:
                logger.info(f"WebSocket disconnected: {connection_id}")
            except Exception as e:
                logger.error(f"Error with WebSocket {connection_id}: {e}", exc_info=True)
            finally:
                await websocket_manager.disconnect(connection_id)
                logger.info(f"WebSocket connection {connection_id} closed.")


@frontend_agent.subscribe(
    channel=human_channel,
    filter_by_message=lambda message: message.get("type") == "agent_message",
)
@traced_handler("handle_human_messages")
async def handle_human_messages(message: TracedMessage):
    agent = message.data.get("agent")
    content = message.data.get("message")
    connection_id = message.data.get("connection_id")

    if connection_id not in messages_cache:
        messages_cache[connection_id] = []

    messages_cache[connection_id].append(
        {
            "role": "assistant",
            "content": content,
            "agent": agent,
            "id": message.id,
        }
    )
    
    await websocket_manager.send_message_to_connection(
        connection_id, {"sender": agent, "content": content}
    )


@frontend_agent.subscribe(channel=human_channel)
async def handle_others(msg: TracedMessage):
    logger.debug(f"Received message type: {msg.type}")