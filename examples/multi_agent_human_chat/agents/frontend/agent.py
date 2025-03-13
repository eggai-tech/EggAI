import os
from eggai import Channel, Agent
from eggai.transport import KafkaTransport, eggai_set_default_transport

from libraries.tracing import TracedMessage
from starlette.websockets import WebSocket, WebSocketDisconnect
import asyncio
import uuid
import uvicorn
from opentelemetry import trace
from fastapi import FastAPI, Query

from libraries.tracing.otel import get_traceparent_from_connection_id, traced_handler
from .websocket_manager import WebSocketManager
from .config import settings
from libraries.logger import get_console_logger

logger = get_console_logger("frontend_agent")

# Load environment variable
GUARDRAILS_ENABLED = os.getenv("GUARDRAILS_TOKEN") is not None

# Conditionally import guardrails
if GUARDRAILS_ENABLED:
    try:
        from .guardrails import toxic_language_guard
    except ImportError as e:
        raise ImportError("Guardrails is enabled but cannot be imported.") from e
else:
    toxic_language_guard = None  # Assign a no-op function


def create_kafka_transport():
    return KafkaTransport(
        bootstrap_servers=settings.kafka_bootstrap_servers
    )


eggai_set_default_transport(create_kafka_transport)

frontend_agent = Agent("FrontendAgent")

human_channel = Channel("human")

websocket_manager = WebSocketManager()

messages_cache = {}
tracer = trace.get_tracer("frontend_agent")


@tracer.start_as_current_span("add_websocket_gateway")
def add_websocket_gateway(route: str, app: FastAPI, server: uvicorn.Server):
    @app.websocket(route)
    @tracer.start_as_current_span("websocket_handler")
    async def websocket_handler(
            websocket: WebSocket, connection_id: str = Query(None, alias="connection_id")
    ):
        if server.should_exit:
            websocket.state.closed = True
            return
        if connection_id is None:
            connection_id = str(uuid.uuid4())

        if connection_id not in messages_cache:
            messages_cache[connection_id] = []
        await websocket_manager.connect(websocket, connection_id)
        await websocket_manager.send_message_to_connection(
            connection_id, {"connection_id": connection_id}
        )

        trace_parent = get_traceparent_from_connection_id(connection_id)
        try:
            while True:
                try:
                    data = await asyncio.wait_for(websocket.receive_json(), timeout=1)
                except asyncio.TimeoutError:
                    if server.should_exit:
                        await websocket_manager.disconnect(connection_id)
                        # TEMPORARY FIX FOR Bug on asyncio.base_events.Server.wait_closed (see
                        # Close all connections when server is shutting down
                        conns = server.server_state.connections or []
                        for conn in conns:
                            if "shutdown" in dir(conn):
                                conn.shutdown()
                        break
                    continue
                message_id = str(uuid.uuid4())
                content = data.get("payload")

                # Validate content with guardrails if enabled
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
                                tracestate=str(trace.get_current_span().get_span_context().trace_state),
                            )
                        )
                        continue
                else:
                    valid_content = (
                        content  # Pass content through if guardrails is disabled
                    )

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
                        tracestate=str(trace.get_current_span().get_span_context().trace_state),
                    )
                )
        except WebSocketDisconnect:
            pass
        except Exception as e:
            logger.error(f"[WEBSOCKET GATEWAY]: Error with WebSocket {connection_id}: {e}")
        finally:
            await websocket_manager.disconnect(connection_id)
            logger.info(f"[WEBSOCKET GATEWAY]: WebSocket connection {connection_id} closed.")


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
    logger.debug("Received message: %s", msg)
