"""Frontend agent tests."""

import asyncio
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from eggai import Channel
from eggai.transport import eggai_set_default_transport
from fastapi import FastAPI
from starlette.websockets import WebSocket, WebSocketState

# Set up Kafka transport before any agents or channels are created
from ..config import settings
from libraries.kafka_transport import create_kafka_transport

eggai_set_default_transport(
    lambda: create_kafka_transport(
        bootstrap_servers=settings.kafka_bootstrap_servers,
        ssl_cert=settings.kafka_ca_content,
    )
)

from libraries.tracing import TracedMessage
from agents.frontend.types import MessageType
from ..agent import (
    add_websocket_gateway,
    frontend_agent,
    handle_human_messages,
    handle_human_stream_messages,
    websocket_manager,
)
from ..websocket_manager import WebSocketManager

pytestmark = pytest.mark.asyncio

# Mock the WebSocket manager to avoid actual socket connections
websocket_manager.send_message_to_connection = AsyncMock()

# Set up channel for testing
human_channel = Channel("human")


@pytest.fixture
def mock_websocket():
    """Create a mock WebSocket for testing."""
    websocket = MagicMock(spec=WebSocket)
    websocket.accept = AsyncMock()
    websocket.send_json = AsyncMock()
    websocket.receive_json = AsyncMock()
    websocket.close = AsyncMock()
    websocket.state = MagicMock()
    websocket.state.closed = False
    websocket.client_state = WebSocketState.CONNECTED
    return websocket


@pytest.fixture
def mock_server():
    """Create a mock uvicorn server for testing."""
    server = MagicMock()
    server.should_exit = False
    server.server_state = MagicMock()
    server.server_state.connections = []
    return server


@pytest.fixture
def test_app():
    """Create a test FastAPI app."""
    return FastAPI()


@pytest.fixture
def connection_id():
    """Generate a test connection ID."""
    return str(uuid.uuid4())


@pytest.fixture
def message_id():
    """Generate a test message ID."""
    return str(uuid.uuid4())


@pytest.mark.asyncio
async def test_frontend_agent():
    await frontend_agent.start()

    # Create test data
    connection_id = str(uuid.uuid4())
    message_id = str(uuid.uuid4())

    # Create a test message
    test_message = TracedMessage(
        id=message_id,
        type=MessageType.AGENT_MESSAGE.value,
        source="triage_agent",
        data={
            "message": "Hello, how can I help you?",
            "connection_id": connection_id,
            "agent": "TriageAgent",
        },
    )

    # Publish message to channel
    await human_channel.publish(test_message)

    # Wait for async processing
    await asyncio.sleep(0.5)

    # Verify the message was sent to the WebSocket
    websocket_manager.send_message_to_connection.assert_called_with(
        connection_id,
        {
            "sender": "TriageAgent",
            "content": "Hello, how can I help you?",
            "type": MessageType.ASSISTANT_MESSAGE.value,
        },
    )

    # Reset mock for future tests
    websocket_manager.send_message_to_connection.reset_mock()


@pytest.mark.asyncio
async def test_handle_human_stream_messages_start():
    """Test handling stream start messages."""
    connection_id = str(uuid.uuid4())
    message_id = str(uuid.uuid4())

    # Mock websocket manager
    with patch.object(
        websocket_manager, "send_message_to_connection", new_callable=AsyncMock
    ) as mock_send:
        message = TracedMessage(
            id=message_id,
            type=MessageType.AGENT_MESSAGE_STREAM_START.value,
            source="TestAgent",
            data={
                "message_id": message_id,
                "connection_id": connection_id,
            },
        )

        await handle_human_stream_messages(message)

        mock_send.assert_called_once_with(
            connection_id,
            {
                "sender": "TestAgent",
                "content": "",
                "type": MessageType.ASSISTANT_MESSAGE_STREAM_START.value,
            },
        )


@pytest.mark.asyncio
async def test_handle_human_stream_messages_chunk():
    """Test handling stream chunk messages."""
    connection_id = str(uuid.uuid4())
    message_id = str(uuid.uuid4())

    with patch.object(
        websocket_manager, "send_message_to_connection", new_callable=AsyncMock
    ) as mock_send:
        message = TracedMessage(
            id=message_id,
            type=MessageType.AGENT_MESSAGE_STREAM_CHUNK.value,
            source="TestAgent",
            data={
                "message_id": message_id,
                "connection_id": connection_id,
                "message_chunk": "Hello",
                "chunk_index": 1,
            },
        )

        await handle_human_stream_messages(message)

        mock_send.assert_called_once_with(
            connection_id,
            {
                "sender": "TestAgent",
                "content": "Hello",
                "chunk_index": 1,
                "type": MessageType.ASSISTANT_MESSAGE_STREAM_CHUNK.value,
            },
        )


@pytest.mark.asyncio
async def test_handle_human_stream_messages_end():
    """Test handling stream end messages."""
    connection_id = str(uuid.uuid4())
    message_id = str(uuid.uuid4())

    # Initialize chat history cache
    websocket_manager.chat_messages[connection_id] = []

    with patch.object(
        websocket_manager, "send_message_to_connection", new_callable=AsyncMock
    ) as mock_send:
        message = TracedMessage(
            id=message_id,
            type=MessageType.AGENT_MESSAGE_STREAM_END.value,
            source="TestAgent",
            data={
                "message_id": message_id,
                "connection_id": connection_id,
                "message": "Complete response",
            },
        )

        await handle_human_stream_messages(message)

        # Check message was added to chat history
        assert len(websocket_manager.chat_messages[connection_id]) == 1
        assert websocket_manager.chat_messages[connection_id][0]["content"] == "Complete response"
        assert websocket_manager.chat_messages[connection_id][0]["agent"] == "TestAgent"

        mock_send.assert_called_once_with(
            connection_id,
            {
                "sender": "TestAgent",
                "content": "Complete response",
                "type": MessageType.ASSISTANT_MESSAGE_STREAM_END.value,
            },
        )


@pytest.mark.asyncio
async def test_handle_human_stream_messages_waiting():
    """Test handling stream waiting messages."""
    connection_id = str(uuid.uuid4())
    message_id = str(uuid.uuid4())

    with patch.object(
        websocket_manager, "send_message_to_connection", new_callable=AsyncMock
    ) as mock_send:
        message = TracedMessage(
            id=message_id,
            type=MessageType.AGENT_MESSAGE_STREAM_WAITING_MESSAGE.value,
            source="TestAgent",
            data={
                "message_id": message_id,
                "connection_id": connection_id,
                "message": "Please wait...",
            },
        )

        await handle_human_stream_messages(message)

        mock_send.assert_called_once_with(
            connection_id,
            {
                "sender": "TestAgent",
                "content": "Please wait...",
                "type": MessageType.ASSISTANT_MESSAGE_STREAM_WAITING_MESSAGE.value,
            },
        )


@pytest.mark.asyncio
async def test_handle_human_messages():
    """Test handling regular human messages."""
    connection_id = str(uuid.uuid4())
    message_id = str(uuid.uuid4())

    # Initialize chat history cache
    websocket_manager.chat_messages[connection_id] = []

    with patch.object(
        websocket_manager, "send_message_to_connection", new_callable=AsyncMock
    ) as mock_send:
        message = TracedMessage(
            id=message_id,
            type=MessageType.AGENT_MESSAGE.value,
            source="TestAgent",
            data={
                "message_id": message_id,
                "connection_id": connection_id,
                "message": "Hello user",
                "agent": "TestAgent",
            },
        )

        await handle_human_messages(message)

        # Check message was added to chat history
        assert len(websocket_manager.chat_messages[connection_id]) == 1
        assert websocket_manager.chat_messages[connection_id][0]["content"] == "Hello user"
        assert websocket_manager.chat_messages[connection_id][0]["agent"] == "TestAgent"

        mock_send.assert_called_once_with(
            connection_id,
            {
                "sender": "TestAgent",
                "content": "Hello user",
                "type": MessageType.ASSISTANT_MESSAGE.value,
            },
        )


@pytest.mark.asyncio
async def test_handle_human_messages_new_connection():
    """Test handling messages for new connections."""
    connection_id = str(uuid.uuid4())
    message_id = str(uuid.uuid4())

    # Ensure chat history is empty for new connection
    websocket_manager.chat_messages.pop(connection_id, None)

    with patch.object(
        websocket_manager, "send_message_to_connection", new_callable=AsyncMock
    ) as mock_send:
        message = TracedMessage(
            id=message_id,
            type="agent_message",
            source="TestAgent",
            data={
                "message_id": message_id,
                "connection_id": connection_id,
                "message": "Welcome",
                "agent": "TestAgent",
            },
        )

        await handle_human_messages(message)

        # Check chat history cache was initialized and message added
        assert connection_id in websocket_manager.chat_messages
        assert len(websocket_manager.chat_messages[connection_id]) == 1
        assert websocket_manager.chat_messages[connection_id][0]["content"] == "Welcome"


def test_add_websocket_gateway(test_app, mock_server):
    """Test adding websocket gateway to FastAPI app."""
    # Test that the function doesn't raise an error
    add_websocket_gateway("/ws", test_app, mock_server)

    # Check that a websocket route was added
    websocket_routes = [
        route
        for route in test_app.routes
        if hasattr(route, "path") and route.path == "/ws"
    ]
    assert len(websocket_routes) > 0


@pytest.mark.asyncio
async def test_websocket_manager_connect(mock_websocket, connection_id):
    """Test WebSocket manager connection."""
    manager = WebSocketManager()

    result = await manager.connect(mock_websocket, connection_id)

    assert result == connection_id
    assert connection_id in manager.active_connections
    assert manager.active_connections[connection_id] == mock_websocket
    mock_websocket.accept.assert_called_once()


@pytest.mark.asyncio
async def test_websocket_manager_disconnect(mock_websocket, connection_id):
    """Test WebSocket manager disconnection."""
    manager = WebSocketManager()
    manager.active_connections[connection_id] = mock_websocket

    await manager.disconnect(connection_id)

    assert connection_id not in manager.active_connections
    mock_websocket.close.assert_called_once_with(
        code=1001, reason="Connection closed by server"
    )


@pytest.mark.asyncio
async def test_websocket_manager_send_message(mock_websocket, connection_id):
    """Test sending message through WebSocket manager."""
    manager = WebSocketManager()
    manager.active_connections[connection_id] = mock_websocket

    message_data = {"type": "test", "content": "Hello"}

    # Mock the logger import to avoid import issues
    with patch("libraries.logger.get_console_logger") as mock_logger:
        mock_logger.return_value = MagicMock()
        await manager.send_message_to_connection(connection_id, message_data)

    mock_websocket.send_json.assert_called_once_with(message_data)


@pytest.mark.asyncio
async def test_websocket_manager_send_message_no_connection(connection_id):
    """Test sending message when connection doesn't exist."""
    manager = WebSocketManager()

    message_data = {"type": "test", "content": "Hello"}
    with patch("libraries.logger.get_console_logger") as mock_logger:
        mock_logger.return_value = MagicMock()
        await manager.send_message_to_connection(connection_id, message_data)

    # Message should be buffered
    assert connection_id in manager.message_buffers
    assert message_data in manager.message_buffers[connection_id]


@pytest.mark.asyncio
async def test_websocket_manager_attach_message_id(connection_id, message_id):
    """Test attaching message ID to connection."""
    manager = WebSocketManager()

    await manager.attach_message_id(message_id, connection_id)

    assert manager.message_ids[message_id] == connection_id


@pytest.mark.asyncio
async def test_websocket_manager_send_to_message_id(
    mock_websocket, connection_id, message_id
):
    """Test sending message by message ID."""
    manager = WebSocketManager()
    manager.active_connections[connection_id] = mock_websocket
    manager.message_ids[message_id] = connection_id

    message_data = {"type": "test", "content": "Hello"}

    # Mock the logger import to avoid import issues
    with patch("libraries.logger.get_console_logger") as mock_logger:
        mock_logger.return_value = MagicMock()
        await manager.send_to_message_id(message_id, message_data)

    mock_websocket.send_json.assert_called_once_with(message_data)


@pytest.mark.asyncio
async def test_websocket_manager_get_connection_id_from_message_id(
    connection_id, message_id
):
    """Test getting connection ID from message ID."""
    manager = WebSocketManager()
    manager.message_ids[message_id] = connection_id

    result = await manager.get_connection_id_from_message_id(message_id)

    assert result == connection_id


@pytest.mark.asyncio
async def test_websocket_manager_broadcast_message():
    """Test broadcasting message to all connections."""
    manager = WebSocketManager()

    # Create multiple mock websockets
    mock_ws1 = MagicMock(spec=WebSocket)
    mock_ws1.send_json = AsyncMock()
    mock_ws2 = MagicMock(spec=WebSocket)
    mock_ws2.send_json = AsyncMock()

    manager.active_connections["conn1"] = mock_ws1
    manager.active_connections["conn2"] = mock_ws2

    message_data = {"type": "broadcast", "content": "Hello all"}
    await manager.broadcast_message(message_data)

    mock_ws1.send_json.assert_called_once_with(message_data)
    mock_ws2.send_json.assert_called_once_with(message_data)


@pytest.mark.asyncio
async def test_websocket_manager_disconnect_all():
    """Test disconnecting all connections."""
    manager = WebSocketManager()

    # Create multiple mock websockets
    mock_ws1 = MagicMock(spec=WebSocket)
    mock_ws1.close = AsyncMock()
    mock_ws1.state = MagicMock()
    mock_ws1.state.closed = False
    mock_ws1.client_state = WebSocketState.CONNECTED

    mock_ws2 = MagicMock(spec=WebSocket)
    mock_ws2.close = AsyncMock()
    mock_ws2.state = MagicMock()
    mock_ws2.state.closed = False
    mock_ws2.client_state = WebSocketState.CONNECTED

    manager.active_connections["conn1"] = mock_ws1
    manager.active_connections["conn2"] = mock_ws2

    await manager.disconnect_all()

    assert len(manager.active_connections) == 0
    mock_ws1.close.assert_called_once_with(
        code=1001, reason="Connection closed by server"
    )
    mock_ws2.close.assert_called_once_with(
        code=1001, reason="Connection closed by server"
    )


@pytest.mark.asyncio
async def test_websocket_manager_connect_with_buffered_messages(
    mock_websocket, connection_id
):
    """Test connecting when there are buffered messages."""
    manager = WebSocketManager()

    # Add buffered messages
    buffered_message = {"type": "buffered", "content": "Buffered message"}
    manager.message_buffers[connection_id].append(buffered_message)

    await manager.connect(mock_websocket, connection_id)

    # Check that buffered message was sent
    mock_websocket.send_json.assert_called_with(buffered_message)
    # Check that buffer was cleared
    assert len(manager.message_buffers[connection_id]) == 0


@pytest.mark.asyncio
async def test_websocket_manager_send_message_error(mock_websocket, connection_id):
    """Test handling error when sending message."""
    manager = WebSocketManager()
    manager.active_connections[connection_id] = mock_websocket

    # Make send_json raise an exception
    mock_websocket.send_json.side_effect = Exception("Send failed")

    message_data = {"type": "test", "content": "Hello"}

    # Mock the logger import to avoid import issues
    with patch("libraries.logger.get_console_logger") as mock_logger:
        mock_logger.return_value = MagicMock()
        # Should not raise exception
        await manager.send_message_to_connection(connection_id, message_data)

    mock_websocket.send_json.assert_called_once_with(message_data)


@pytest.mark.asyncio
async def test_websocket_manager_disconnect_already_closed(connection_id):
    """Test disconnecting already closed connection."""
    manager = WebSocketManager()

    mock_websocket = MagicMock(spec=WebSocket)
    mock_websocket.state = MagicMock()
    mock_websocket.state.closed = True
    mock_websocket.client_state = WebSocketState.DISCONNECTED
    mock_websocket.close = AsyncMock()

    manager.active_connections[connection_id] = mock_websocket

    await manager.disconnect(connection_id)

    # Should not try to close already closed connection
    mock_websocket.close.assert_not_called()
    assert connection_id not in manager.active_connections


def test_websocket_manager_initialization():
    """Test WebSocket manager initialization."""
    manager = WebSocketManager()

    assert isinstance(manager.active_connections, dict)
    assert isinstance(manager.message_buffers, dict)
    assert isinstance(manager.message_ids, dict)
    assert isinstance(manager.streaming_messages, dict)
    assert len(manager.active_connections) == 0
