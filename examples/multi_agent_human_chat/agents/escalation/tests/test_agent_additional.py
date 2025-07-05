"""Additional tests for escalation agent to improve coverage."""

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from dotenv import load_dotenv

from agents.escalation.agent import (
    get_conversation_string,
    handle_other_messages,
    handle_ticketing_request,
    process_escalation_request,
)
from agents.escalation.config import (
    MSG_TYPE_STREAM_END,
    MSG_TYPE_TICKETING_REQUEST,
)
from libraries.tracing import TracedMessage


@pytest.mark.asyncio
async def test_escalation_agent_error_handling(monkeypatch):
    """Test error handling in escalation agent."""
    load_dotenv()

    def mock_escalation_error(*args, **kwargs):
        async def error_generator():
            raise Exception("Escalation module error")

        return error_generator()

    monkeypatch.setattr(
        "agents.escalation.agent.escalation_optimized_dspy", mock_escalation_error
    )

    from agents.escalation.agent import human_stream_channel

    mock_publish = AsyncMock()
    monkeypatch.setattr(human_stream_channel, "publish", mock_publish)

    test_message = TracedMessage(
        id=str(uuid4()),
        type=MSG_TYPE_TICKETING_REQUEST,
        source="TestAgent",
        data={
            "chat_messages": [
                {"role": "user", "content": "I need to speak to a manager"}
            ],
            "connection_id": str(uuid4()),
            "message_id": str(uuid4()),
        },
    )

    await handle_ticketing_request(test_message)

    assert mock_publish.called
    assert mock_publish.call_count >= 2

    end_messages = [
        call
        for call in mock_publish.call_args_list
        if call[0][0].type == MSG_TYPE_STREAM_END
    ]
    assert len(end_messages) > 0

    error_msg = end_messages[0][0][0].data.get("message", "")
    assert any(word in error_msg.lower() for word in ["error", "sorry", "trouble"])


@pytest.mark.asyncio
async def test_escalation_empty_chat_messages(monkeypatch):
    """Test handling of empty chat messages."""
    load_dotenv()

    from agents.escalation.agent import human_stream_channel

    mock_publish = AsyncMock()
    monkeypatch.setattr(human_stream_channel, "publish", mock_publish)

    async def mock_response(*args, **kwargs):
        from dspy import Prediction

        yield Prediction(final_response="I need more information to help you")

    monkeypatch.setattr(
        "agents.escalation.agent.escalation_optimized_dspy", mock_response
    )

    test_message = TracedMessage(
        id=str(uuid4()),
        type=MSG_TYPE_TICKETING_REQUEST,
        source="TestAgent",
        data={
            "chat_messages": [],
            "connection_id": str(uuid4()),
            "message_id": str(uuid4()),
        },
    )

    await handle_ticketing_request(test_message)

    assert mock_publish.called
    assert mock_publish.call_count >= 2


@pytest.mark.asyncio
async def test_escalation_missing_connection_id(monkeypatch):
    """Test handling of missing connection_id."""
    load_dotenv()

    from agents.escalation.agent import human_stream_channel

    mock_publish = AsyncMock()
    monkeypatch.setattr(human_stream_channel, "publish", mock_publish)

    test_message = TracedMessage(
        id=str(uuid4()),
        type=MSG_TYPE_TICKETING_REQUEST,
        source="TestAgent",
        data={
            "chat_messages": [{"role": "user", "content": "test"}],
            "message_id": str(uuid4()),
        },
    )

    await handle_ticketing_request(test_message)

    assert mock_publish.called
    for call in mock_publish.call_args_list:
        msg = call[0][0]
        assert msg.data.get("connection_id") is not None


@pytest.mark.asyncio
async def test_handle_other_messages():
    """Test the handle_other_messages function."""
    test_message = TracedMessage(
        id=str(uuid4()),
        type="debug_message",
        source="TestAgent",
        data={"content": "debug info"},
    )

    await handle_other_messages(test_message)


def test_get_conversation_string_empty():
    """Test get_conversation_string with empty messages."""
    result = get_conversation_string([])
    assert result == ""


def test_get_conversation_string_missing_content():
    """Test get_conversation_string with missing content field."""
    messages = [{"role": "user"}, {"role": "assistant", "content": "Hello"}]
    result = get_conversation_string(messages)
    assert "assistant: Hello" in result
    assert "user:" not in result.lower()


def test_get_conversation_string_normal():
    """Test get_conversation_string with normal messages."""
    messages = [
        {"role": "user", "content": "Hi"},
        {"role": "assistant", "content": "Hello"},
    ]
    result = get_conversation_string(messages)
    assert "user: Hi" in result
    assert "assistant: Hello" in result


@pytest.mark.asyncio
async def test_process_escalation_streaming_error(monkeypatch):
    """Test error handling during streaming."""
    load_dotenv()

    from agents.escalation.agent import human_stream_channel

    mock_publish = AsyncMock()
    monkeypatch.setattr(human_stream_channel, "publish", mock_publish)

    async def mock_streaming_error(*args, **kwargs):
        from dspy.streaming import StreamResponse

        yield StreamResponse(
            chunk="First chunk", predict_name="test", signature_field_name="response"
        )
        raise Exception("Streaming error")

    monkeypatch.setattr(
        "agents.escalation.agent.escalation_optimized_dspy", mock_streaming_error
    )

    connection_id = str(uuid4())
    message_id = str(uuid4())
    conversation_str = "User: I need help with my policy"

    await process_escalation_request(conversation_str, connection_id, message_id)

    assert mock_publish.call_count >= 2

    end_messages = [
        call
        for call in mock_publish.call_args_list
        if call[0][0].type == MSG_TYPE_STREAM_END
    ]
    assert len(end_messages) > 0


@pytest.mark.asyncio
async def test_escalation_missing_data_fields(monkeypatch):
    """Test handling of missing various data fields."""
    load_dotenv()

    from agents.escalation.agent import human_stream_channel

    mock_publish = AsyncMock()
    monkeypatch.setattr(human_stream_channel, "publish", mock_publish)

    test_message = TracedMessage(
        id=str(uuid4()),
        type=MSG_TYPE_TICKETING_REQUEST,
        source="TestAgent",
        data={},
    )

    await handle_ticketing_request(test_message)

    assert mock_publish.called


@pytest.mark.asyncio
async def test_escalation_exception_in_handler(monkeypatch):
    """Test exception handling in main handler."""
    load_dotenv()

    from agents.escalation.agent import human_stream_channel

    mock_publish = AsyncMock()
    monkeypatch.setattr(human_stream_channel, "publish", mock_publish)

    def mock_error(*args, **kwargs):
        raise Exception("Unexpected error")

    monkeypatch.setattr("agents.escalation.agent.get_conversation_string", mock_error)

    test_message = TracedMessage(
        id=str(uuid4()),
        type="escalation_request",
        source="TestAgent",
        data={
            "chat_messages": [{"role": "user", "content": "test"}],
            "connection_id": str(uuid4()),
        },
    )

    await handle_ticketing_request(test_message)

    assert mock_publish.called


@pytest.mark.asyncio
async def test_escalation_long_conversation(monkeypatch):
    """Test handling of long conversation context."""
    load_dotenv()

    from agents.escalation.agent import human_stream_channel

    mock_publish = AsyncMock()
    monkeypatch.setattr(human_stream_channel, "publish", mock_publish)

    async def mock_response(*args, **kwargs):
        from dspy import Prediction

        yield Prediction(final_response="I understand your concern. Let me help you.")

    monkeypatch.setattr(
        "agents.escalation.agent.escalation_optimized_dspy", mock_response
    )

    chat_messages = []
    for i in range(20):
        chat_messages.append({"role": "user", "content": f"Message {i}"})
        chat_messages.append({"role": "assistant", "content": f"Response {i}"})

    test_message = TracedMessage(
        id=str(uuid4()),
        type=MSG_TYPE_TICKETING_REQUEST,
        source="TestAgent",
        data={
            "chat_messages": chat_messages,
            "connection_id": str(uuid4()),
            "message_id": str(uuid4()),
        },
    )

    await handle_ticketing_request(test_message)

    assert mock_publish.called
    assert mock_publish.call_count >= 2

    end_messages = [
        call
        for call in mock_publish.call_args_list
        if call[0][0].type == MSG_TYPE_STREAM_END
    ]
    assert len(end_messages) == 1
    assert (
        end_messages[0][0][0].data["message"]
        == "I understand your concern. Let me help you."
    )
