from collections import defaultdict
from typing import Dict

from starlette.websockets import WebSocket, WebSocketState


class WebSocketManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.message_buffers: Dict[str, list] = defaultdict(list)
        self.message_ids: Dict[str, str] = defaultdict(str)

    async def connect(self, websocket: WebSocket, connection_id: str):
        await websocket.accept()
        if connection_id in self.active_connections:
            await self.disconnect(connection_id)
        self.active_connections[connection_id] = websocket
        if connection_id not in self.message_buffers:
            self.message_buffers[connection_id] = []

        websocket.state.closed = False

        if self.message_buffers[connection_id]:
            for message in self.message_buffers[connection_id]:
                await websocket.send_json(message)
            self.message_buffers[connection_id].clear()

        return connection_id

    async def disconnect(self, connection_id: str):
        connection = self.active_connections.get(connection_id)
        if connection:
            if not connection.state.closed:
                connection.state.closed = True
                if connection.client_state is not WebSocketState.DISCONNECTED:
                    await connection.close(
                        code=1001, reason="Connection closed by server"
                    )
        self.active_connections.pop(connection_id, None)

    async def send_message_to_connection(self, connection_id: str, message_data: dict):
        connection = self.active_connections.get(connection_id)
        if connection:
            await connection.send_json(message_data)
        else:
            self.message_buffers[connection_id].append(message_data)

    async def attach_message_id(self, message_id: str, connection_id: str):
        self.message_ids[message_id] = connection_id

    async def send_to_message_id(self, message_id: str, message_data: dict):
        session_id = self.message_ids.get(message_id)
        if session_id:
            await self.send_message_to_connection(session_id, message_data)

    async def get_connection_id_from_message_id(self, message_id: str):
        return self.message_ids.get(message_id)

    async def broadcast_message(self, message_data: dict):
        for _, connection in self.active_connections.items():
            await connection.send_json(message_data)

    async def disconnect_all(self):
        for connection_id in list(self.active_connections.keys()):
            await self.disconnect(connection_id)
