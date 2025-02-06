import os
from eggai import Channel, Agent
from starlette.websockets import WebSocket, WebSocketDisconnect
import asyncio
import uuid
import uvicorn
from fastapi import FastAPI, Query
from .websocket_manager import WebSocketManager

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

frontend_agent = Agent("FrontendAgent")

human_channel = Channel("human")

websocket_manager = WebSocketManager()

messages_cache = {}


def add_websocket_gateway(route: str, app: FastAPI, server: uvicorn.Server):
    @app.websocket(route)
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
                            {
                                "id": message_id,
                                "type": "agent_message",
                                "payload": "Sorry, I can't help you with that.",
                                "meta": {
                                    "agent": "TriageAgent",
                                    "connection_id": connection_id,
                                },
                            }
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
                    {
                        "id": message_id,
                        "type": "user_message",
                        "payload": {"chat_messages": messages_cache[connection_id]},
                        "meta": {
                            "connection_id": connection_id,
                        },
                    }
                )
        except WebSocketDisconnect:
            pass
        except Exception as e:
            print(f"[WEBSOCKET GATEWAY]: Error with WebSocket {connection_id}: {e}")
        finally:
            await websocket_manager.disconnect(connection_id)
            print(f"[WEBSOCKET GATEWAY]: WebSocket connection {connection_id} closed.")


@frontend_agent.subscribe(
    channel=human_channel,
    filter_func=lambda message: message.get("type") == "agent_message",
)
async def handle_human_messages(message):
    meta = message.get("meta")
    agent = meta.get("agent")
    content = message.get("payload")
    connection_id = meta.get("connection_id")
    if connection_id not in messages_cache:
        messages_cache[connection_id] = []
    messages_cache[connection_id].append(
        {
            "role": "assistant",
            "content": content,
            "agent": agent,
            "id": message.get("id"),
        }
    )
    await websocket_manager.send_message_to_connection(
        connection_id, {"sender": agent, "content": content}
    )
