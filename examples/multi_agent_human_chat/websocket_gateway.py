import asyncio
import uuid

import uvicorn
from eggai import Channel, Agent
from fastapi import FastAPI, Query
from starlette.websockets import WebSocket, WebSocketDisconnect

from websocket_manager import WebSocketManager

websocket_manager = WebSocketManager()
human_channel = Channel("human")
websocket_gateway_agent = Agent("WebSocketGateway")


@websocket_gateway_agent.subscribe(channel=human_channel, filter_func=lambda message: message.get("type") == "agent_message")
async def handle_human_messages(message):
    meta = message.get("meta")
    agent = meta.get("agent")
    content = message.get("payload")
    connection_id = meta.get("connection_id")
    if not messages_cache[connection_id]:
        messages_cache[connection_id] = []
    messages_cache[connection_id].append({"role": "assistant", "content": content, "agent": agent, "id": message.get("id")})
    await websocket_manager.send_message_to_connection(connection_id, { "sender": agent, "content": content })

messages_cache = {}

def add_websocket_gateway(route: str, app: FastAPI, server: uvicorn.Server):
    @app.websocket(route)
    async def websocket_handler(websocket: WebSocket, connection_id: str = Query(None, alias="connection_id")):
        if connection_id is None:
            connection_id = str(uuid.uuid4())

        if connection_id not in messages_cache:
            messages_cache[connection_id] = []
        await websocket_manager.connect(websocket, connection_id)
        await websocket_manager.send_message_to_connection(connection_id, {"connection_id": connection_id})
        try:
            while True:
                try:
                    data = await asyncio.wait_for(websocket.receive_json(), timeout=1)
                except asyncio.TimeoutError:
                    if server.should_exit:
                        break
                    continue
                message_id = str(uuid.uuid4())
                content = data.get("payload")
                await websocket_manager.attach_message_id(message_id, connection_id)
                messages_cache[connection_id].append(
                    {"role": "user", "content": content, "id": message_id, "agent": "User"})
                await human_channel.publish({
                    "id": message_id,
                    "type": "user_message",
                    "payload": {
                        "chat_messages": messages_cache[connection_id]
                    },
                    "meta": {
                        "connection_id": connection_id,
                    }
                })
        except WebSocketDisconnect:
            pass
        except Exception as e:
            print(f"[WEBSOCKET GATEWAY]: Error with WebSocket {connection_id}: {e}")
        finally:
            await websocket_manager.disconnect(connection_id)
            print(f"[WEBSOCKET GATEWAY]: WebSocket connection {connection_id} closed.")
