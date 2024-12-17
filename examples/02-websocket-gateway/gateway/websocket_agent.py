import uuid

from eggai import Channel, Agent
from fastapi import FastAPI, Query
from starlette.websockets import WebSocket, WebSocketDisconnect

from .websocket_manager import WebSocketManager

websocket_manager = WebSocketManager()
human_channel = Channel("human")
websocket_gateway_agent = Agent("WebSocketGateway")


@websocket_gateway_agent.subscribe(channel=human_channel)
async def handle_human_messages(message):
    await websocket_manager.send_to_message_id(message.get("id"), message)


def plug_fastapi_websocket(route: str, app: FastAPI):
    @app.websocket(route)
    async def websocket_handler(websocket: WebSocket, connection_id: str = Query(None, alias="connection_id")):
        if connection_id is None:
            connection_id = str(uuid.uuid4())
        await websocket_manager.connect(websocket, connection_id)
        await websocket_manager.send_message_to_connection(connection_id, {"connection_id": connection_id})
        try:
            while True:
                data = await websocket.receive_json()
                message_id = str(uuid.uuid4())
                await websocket_manager.attach_message_id(message_id, connection_id)
                await human_channel.publish({
                    "id": message_id,
                    "type": data.get("type"),
                    "payload": data.get("payload")
                })
        except WebSocketDisconnect:
            pass
        except Exception as e:
            print(f"[WEBSOCKET GATEWAY]: Error with WebSocket {connection_id}: {e}")
        finally:
            await websocket_manager.disconnect(connection_id)
            print(f"[WEBSOCKET GATEWAY]: WebSocket connection {connection_id} closed.")


async def start_websocket_gateway():
    await websocket_gateway_agent.run()

async def stop_websocket_gateway():
    await websocket_gateway_agent.stop()