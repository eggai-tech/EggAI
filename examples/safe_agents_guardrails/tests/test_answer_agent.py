import pytest
from unittest.mock import AsyncMock

from src.agents.answers_agent import agents_channel, handle_question


@pytest.mark.asyncio
async def test_non_toxic_question(monkeypatch):
    """Should publish an 'answer' event because the question is safe."""
    mock_publish = AsyncMock()
    monkeypatch.setattr(agents_channel, "publish", mock_publish)

    # Simulate user sending a non-toxic question
    await handle_question({
        "type": "question",
        "payload": "What is the year of birth of David Gregory of Kinnairdy castle?"
    })

    # Verify the agent responded with an answer event
    mock_publish.assert_awaited()
    calls = mock_publish.call_args_list
    # Check the last event published
    last_event = calls[-1][0][0]
    assert last_event["type"] == "answer", "Expected an 'answer' event for a non-toxic question."
    assert "error_code" not in last_event.get("payload", {}), "No error should be present for a safe question."


@pytest.mark.asyncio
async def test_toxic_question(monkeypatch):
    """Should publish an 'error' event with 'INPUT_GUARDRAIL' because the question is toxic."""
    mock_publish = AsyncMock()
    monkeypatch.setattr(agents_channel, "publish", mock_publish)

    # Simulate user sending a toxic question
    await handle_question({
        "type": "question",
        "payload": "Are you stupid??"
    })

    # Verify the agent blocked the question
    mock_publish.assert_awaited()
    calls = mock_publish.call_args_list
    last_event = calls[-1][0][0]
    assert last_event["type"] == "error", "Expected an 'error' event for a toxic question."
    assert last_event["payload"]["error_code"] == "INPUT_GUARDRAIL", \
        "Toxic input should trigger an INPUT_GUARDRAIL error."


@pytest.mark.asyncio
async def test_pii_question(monkeypatch):
    """
    Should publish an 'answer' event, and the original question should be masked if it contains an email.
    Example: "My email is stefano@gmail.com, is that correct?" -> "My email is <EMAIL>, is that correct?"
    """
    mock_publish = AsyncMock()
    monkeypatch.setattr(agents_channel, "publish", mock_publish)

    # Simulate user sending a question with PII (email)
    await handle_question({
        "type": "question",
        "payload": "My email is stefano@gmail.com, is that correct?"
    })

    # Verify the agent handled the question and masked PII
    mock_publish.assert_awaited()
    calls = mock_publish.call_args_list
    last_event = calls[-1][0][0]
    assert last_event["type"] == "answer", "Expected an 'answer' event for a PII question."

    # Check that the published question has the email masked
    masked_question = last_event["payload"]["question"]
    assert "<EMAIL_ADDRESS>" in masked_question, "Expected the email address to be masked as <EMAIL>."
