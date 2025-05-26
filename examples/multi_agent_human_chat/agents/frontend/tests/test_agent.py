"""Frontend agent tests."""
import asyncio
import uuid
from unittest.mock import AsyncMock

import pytest
from eggai import Channel
from eggai.transport import eggai_set_default_transport

# Set up Kafka transport before any agents or channels are created
from agents.frontend.config import settings
from libraries.kafka_transport import create_kafka_transport

eggai_set_default_transport(
    lambda: create_kafka_transport(
        bootstrap_servers=settings.kafka_bootstrap_servers,
        ssl_cert=settings.kafka_ca_content
    )
)

from libraries.tracing import TracedMessage

from ..agent import frontend_agent, websocket_manager

pytestmark = pytest.mark.asyncio

# Mock the WebSocket manager to avoid actual socket connections
websocket_manager.send_message_to_connection = AsyncMock()

# Set up channel for testing
human_channel = Channel("human")


@pytest.mark.asyncio
async def test_frontend_agent():
    await frontend_agent.start()

    # Create test data
    connection_id = str(uuid.uuid4())
    message_id = str(uuid.uuid4())

    # Create a test message
    test_message = TracedMessage(
        id=message_id,
        type="agent_message",
        source="triage_agent",
        data={
            "message": "Hello, how can I help you?",
            "connection_id": connection_id,
            "agent": "TriageAgent",
        }
    )

    # Publish message to channel
    await human_channel.publish(test_message)

    # Wait for async processing
    await asyncio.sleep(0.5)

    # Verify the message was sent to the WebSocket
    websocket_manager.send_message_to_connection.assert_called_with(
        connection_id,
        {"sender": "TriageAgent", "content": "Hello, how can I help you?", "type": "assistant_message"},
    )
    
    # Reset mock for future tests
    websocket_manager.send_message_to_connection.reset_mock()
