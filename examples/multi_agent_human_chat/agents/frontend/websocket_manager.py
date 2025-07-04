"""WebSocket connection manager for the frontend agent."""

from collections import defaultdict
from typing import Dict, Any

from starlette.websockets import WebSocket, WebSocketState

from libraries.logger import get_console_logger


class WebSocketManager:
    def __init__(self) -> None:
        self.logger = get_console_logger("websocket_manager")
        self.active_connections: Dict[str, WebSocket] = {}
        self.message_buffers: Dict[str, list] = defaultdict(list)
        self.message_ids: Dict[str, str] = defaultdict(str)
        self.chat_messages: Dict[str, list] = defaultdict(list)

    async def connect(self, websocket: WebSocket, connection_id: str) -> str:
        """
        Accept a WebSocket connection, register it, and replay any buffered messages.

        Returns the connection ID.
        """
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

    async def disconnect(self, connection_id: str) -> None:
        """Close and remove a WebSocket connection, and clear its chat history."""
        connection = self.active_connections.get(connection_id)
        if connection is not None:
            try:
                if hasattr(connection, "state") and hasattr(connection.state, "closed"):
                    if not connection.state.closed:
                        connection.state.closed = True
                if (
                    hasattr(connection, "client_state")
                    and connection.client_state != WebSocketState.DISCONNECTED
                ):
                    await connection.close(
                        code=1001, reason="Connection closed by server"
                    )
            except Exception:
                # If closing fails, still remove from active connections
                pass
        self.active_connections.pop(connection_id, None)
        self.chat_messages.pop(connection_id, None)

    async def send_message_to_connection(
        self, connection_id: str, message_data: dict
    ) -> None:
        """Send a JSON message to a connection, buffering if it's not active."""

        self.logger.info(f"Sending message to connection {connection_id}: {message_data}")
        connection = self.active_connections.get(connection_id)
        if connection is not None:
            try:
                await connection.send_json(message_data)
                self.logger.info(f"Message sent successfully to connection {connection_id}")
            except Exception as e:
                self.logger.error(
                    f"Error sending message to connection {connection_id}: {e}",
                    exc_info=True,
                )
        else:
            self.logger.warning(f"Connection {connection_id} not found, buffering message")
            self.message_buffers[connection_id].append(message_data)

    async def attach_message_id(self, message_id: str, connection_id: str) -> None:
        """Associate an incoming message ID with a connection ID for reply routing."""
        self.message_ids[message_id] = connection_id

    async def send_to_message_id(self, message_id: str, message_data: dict) -> None:
        """Send a JSON message to the connection associated with a message ID."""
        session_id = self.message_ids.get(message_id)
        if session_id:
            await self.send_message_to_connection(session_id, message_data)

    async def get_connection_id_from_message_id(self, message_id: str) -> str | None:
        """Return the connection ID previously associated with the message ID."""
        return self.message_ids.get(message_id)

    async def broadcast_message(self, message_data: dict) -> None:
        """Broadcast a JSON message to all active WebSocket connections."""
        for _, connection in self.active_connections.items():
            await connection.send_json(message_data)

    async def disconnect_all(self) -> None:
        """Disconnect and cleanup all active WebSocket connections."""
        for connection_id in list(self.active_connections.keys()):
            await self.disconnect(connection_id)
