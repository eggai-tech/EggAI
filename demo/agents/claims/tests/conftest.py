"""Test configuration for claims agent tests."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.fixture(scope="function")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.new_event_loop()
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
def mock_claims_response():
    """Simple mock for claims responses."""

    async def mock_response(*args, **kwargs):
        from dspy import Prediction

        yield Prediction(final_response="I'll help you with your claims request.")

    return mock_response


@pytest.fixture
def mock_stream_channel(monkeypatch):
    """Mock the human stream channel for testing."""
    mock_publish = AsyncMock()
    monkeypatch.setattr(
        "agents.claims.agent.human_stream_channel.publish", mock_publish
    )
    return mock_publish


@pytest.fixture
def mock_human_channel(monkeypatch):
    """Mock the human channel for testing."""
    mock_publish = AsyncMock()
    monkeypatch.setattr("agents.claims.agent.human_channel.publish", mock_publish)
    return mock_publish
