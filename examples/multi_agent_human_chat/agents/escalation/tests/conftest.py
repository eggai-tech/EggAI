import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.fixture(scope="session")
def event_loop():
    """Ensure a fresh event loop for the test session to avoid 'RuntimeError: Event loop is closed'."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop
    loop.close()


@pytest.fixture
def mock_language_model(monkeypatch):
    """Mock the language model to avoid initialization issues in tests."""
    # Mock the language model initialization
    mock_lm = MagicMock()
    monkeypatch.setattr("dspy.LM", lambda *args, **kwargs: mock_lm)
    monkeypatch.setattr(
        "libraries.dspy_set_language_model.dspy_set_language_model",
        lambda *args, **kwargs: mock_lm,
    )
    return mock_lm


@pytest.fixture
def mock_escalation_response():
    """Simple mock for escalation responses."""

    async def mock_response(*args, **kwargs):
        from dspy import Prediction

        yield Prediction(final_response="I'll help you with your escalation request.")

    return mock_response


@pytest.fixture
def mock_stream_channel(monkeypatch):
    """Mock the human stream channel for testing."""
    mock_publish = AsyncMock()
    monkeypatch.setattr(
        "agents.escalation.agent.human_stream_channel.publish", mock_publish
    )
    return mock_publish
