"""
Agent-specific test helpers.

These utilities help with testing EggAI agents and their interactions.
"""

import asyncio
from typing import List, Optional
from uuid import uuid4

from libraries.communication.protocol import ChatMessage, MessageType
from libraries.observability.tracing import TracedMessage


def create_mock_agent_response(
    agent_name: str,
    message: str,
    connection_id: str = "test-connection-123"
) -> TracedMessage:
    """Create a mock agent response for testing."""
    return TracedMessage(
        id=str(uuid4()),
        type=MessageType.AGENT_MESSAGE,
        source=agent_name,
        data={
            "connection_id": connection_id,
            "message": message,
            "agent": agent_name
        }
    )


def create_mock_request_message(
    request_type: MessageType,
    chat_messages: List[ChatMessage],
    connection_id: str = "test-connection-123",
    source: str = "Triage"
) -> TracedMessage:
    """Create a mock request message for testing."""
    return TracedMessage(
        id=str(uuid4()),
        type=request_type,
        source=source,
        data={
            "connection_id": connection_id,
            "chat_messages": chat_messages,
            "timeout": 30.0
        }
    )


async def wait_for_message_with_timeout(
    response_queue: asyncio.Queue,
    timeout: float = 5.0,
    expected_source: Optional[str] = None,
    expected_type: Optional[str] = None
) -> Optional[TracedMessage]:
    """
    Wait for a message in the queue with optional filtering.
    
    Args:
        response_queue: The queue to monitor
        timeout: Maximum time to wait in seconds
        expected_source: If provided, only return messages from this source
        expected_type: If provided, only return messages of this type
    
    Returns:
        The matching message or None if timeout occurs
    """
    try:
        while True:
            message = await asyncio.wait_for(response_queue.get(), timeout=timeout)
            
            # Check if message matches criteria
            if expected_source and message.source != expected_source:
                continue
            if expected_type and message.type != expected_type:
                continue
                
            return message
            
    except asyncio.TimeoutError:
        return None


def create_mock_audit_log(
    message_id: str,
    message_type: str,
    message_source: str,
    channel: str,
    category: str = "Agent Processing"
) -> TracedMessage:
    """Create a mock audit log message for testing."""
    return TracedMessage(
        id=str(uuid4()),
        type=MessageType.AUDIT_LOG,
        source="Audit",
        data={
            "message_id": message_id,
            "message_type": message_type,
            "message_source": message_source,
            "channel": channel,
            "category": category,
            "audit_timestamp": "2024-01-01T00:00:00Z",
            "content": None,
            "error": None
        }
    )


def assert_valid_agent_response(
    response: TracedMessage,
    expected_agent: str,
    connection_id: str = "test-connection-123"
) -> None:
    """Assert that an agent response has the expected structure."""
    assert response.type == MessageType.AGENT_MESSAGE
    assert response.source == expected_agent
    assert response.data["connection_id"] == connection_id
    assert response.data["agent"] == expected_agent
    assert "message" in response.data
    assert isinstance(response.data["message"], str)
    assert len(response.data["message"]) > 0