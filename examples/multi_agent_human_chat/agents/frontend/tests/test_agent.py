import asyncio
import uuid
from unittest.mock import AsyncMock

import pytest
from eggai import Channel

from libraries.tracing import TracedMessage

from ..agent import frontend_agent, websocket_manager

pytestmark = pytest.mark.asyncio

websocket_manager.send_message_to_connection = AsyncMock()

human_channel = Channel("human")


@pytest.mark.asyncio
async def test_frontend_ageny():
    await frontend_agent.start()

    connection_id = str(uuid.uuid4())
    message_id = str(uuid.uuid4())

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

    await human_channel.publish(test_message)

    await asyncio.sleep(0.5)

    websocket_manager.send_message_to_connection.assert_called_with(
        connection_id,
        {"sender": "TriageAgent", "content": "Hello, how can I help you?"},
    )
