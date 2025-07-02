from __future__ import annotations

import asyncio
import uuid

import uvicorn
from fastapi import FastAPI, Query
from opentelemetry import trace
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
from starlette.websockets import WebSocket, WebSocketDisconnect

from libraries.tracing import TracedMessage
from libraries.tracing.otel import safe_set_attribute

from .agent import (
    GUARDRAILS_ENABLED,
    frontend_agent,
    human_channel,
    messages_cache,
    toxic_language_guard,
    tracer,
    websocket_manager,
)

logger = frontend_agent.logger  # reuse agent logger


@tracer.start_as_current_span("add_websocket_gateway")
def add_websocket_gateway(route: str, app: FastAPI, server: uvicorn.Server) -> None:
    """Attach a websocket gateway route to the provided FastAPI app."""

    @app.websocket(route)
    async def websocket_handler(
        websocket: WebSocket, connection_id: str = Query(None, alias="connection_id")
    ) -> None:
        if server.should_exit:
            websocket.state.closed = True
            return

        if connection_id is None:
            connection_id = str(uuid.uuid4())

        if connection_id not in messages_cache:
            messages_cache[connection_id] = []

        propagator = TraceContextTextMapPropagator()
        # Create root span for the connection
        with tracer.start_as_current_span("frontend_chat") as root_span:
            carrier: dict[str, str] = {}
            propagator.inject(carrier)
            trace_parent = carrier.get("traceparent")
            trace_state = carrier.get("tracestate", "")
            safe_set_attribute(root_span, "connection.id", str(connection_id))

        # Extract span context for child spans using propagator
        parent_context = propagator.extract(
            {"traceparent": trace_parent, "tracestate": trace_state}
        )

        with tracer.start_as_current_span(
            "websocket_connection", context=parent_context, kind=trace.SpanKind.SERVER
        ) as span:
            try:
                safe_set_attribute(span, "connection.id", str(connection_id))
                await websocket_manager.connect(websocket, connection_id)
                await websocket_manager.send_message_to_connection(
                    connection_id, {"connection_id": connection_id}
                )

                while True:
                    try:
                        data = await asyncio.wait_for(
                            websocket.receive_json(), timeout=1
                        )
                    except asyncio.TimeoutError:
                        if server.should_exit:
                            await websocket_manager.disconnect(connection_id)
                            conns = server.server_state.connections or []
                            for conn in conns:
                                if hasattr(conn, "shutdown"):
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
                logger.info("WebSocket disconnected: %s", connection_id)
            except RuntimeError as exc:
                logger.error(
                    "WebSocket runtime error for %s: %s", connection_id, exc, exc_info=True
                )
            except Exception as exc:
                logger.error(
                    "Error with WebSocket %s: %s", connection_id, exc, exc_info=True
                )
