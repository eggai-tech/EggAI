"""Additional tests for triage agent to improve coverage."""

from dataclasses import dataclass
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from dotenv import load_dotenv

from agents.triage.agent import handle_others, handle_user_message
from agents.triage.models import TargetAgent
from libraries.tracing import TracedMessage


@dataclass
class MockMetrics:
    """Simple mock for metrics."""

    latency_ms: float = 10.5


@dataclass
class MockClassifierResponse:
    """Simple mock for classifier response."""

    target_agent: TargetAgent
    metrics: MockMetrics


@pytest.mark.asyncio
async def test_triage_agent_error_handling(monkeypatch):
    """Test error handling in triage agent."""
    load_dotenv()

    def mock_classifier(*args, **kwargs):
        raise Exception("Classifier error")

    import agents.triage.agent as triage_module

    monkeypatch.setattr(triage_module, "current_classifier", mock_classifier)

    test_message = TracedMessage(
        id=str(uuid4()),
        type="user_message",
        source="TestTriageAgent",
        data={
            "chat_messages": [{"role": "user", "content": "test message"}],
            "connection_id": str(uuid4()),
            "agent": "TriageAgent",
        },
    )

    await handle_user_message(test_message)


@pytest.mark.asyncio
async def test_triage_agent_missing_data(monkeypatch):
    """Test handling of messages with missing data."""
    load_dotenv()

    from agents.triage.agent import human_stream_channel

    mock_publish = AsyncMock()
    monkeypatch.setattr(human_stream_channel, "publish", mock_publish)

    test_message = TracedMessage(
        id=str(uuid4()),
        type="user_message",
        source="TestTriageAgent",
        data={
            "connection_id": str(uuid4()),
            "agent": "TriageAgent",
        },
    )

    await handle_user_message(test_message)


@pytest.mark.asyncio
async def test_triage_handle_other_messages():
    """Test the handle_others function for non-user messages."""
    test_message = TracedMessage(
        id=str(uuid4()),
        type="debug_message",
        source="TestAgent",
        data={"content": "debug info"},
    )

    await handle_others(test_message)


@pytest.mark.asyncio
async def test_triage_empty_conversation(monkeypatch):
    """Test handling of empty conversation string."""
    load_dotenv()

    from agents.triage.agent import human_stream_channel

    mock_publish = AsyncMock()
    monkeypatch.setattr(human_stream_channel, "publish", mock_publish)

    test_message = TracedMessage(
        id=str(uuid4()),
        type="user_message",
        source="TestTriageAgent",
        data={
            "chat_messages": [],
            "connection_id": str(uuid4()),
            "agent": "TriageAgent",
        },
    )

    await handle_user_message(test_message)


@pytest.mark.asyncio
async def test_triage_malformed_chat_message(monkeypatch):
    """Test handling of malformed chat messages."""
    load_dotenv()

    from agents.triage.agent import human_stream_channel

    mock_publish = AsyncMock()
    monkeypatch.setattr(human_stream_channel, "publish", mock_publish)

    test_message = TracedMessage(
        id=str(uuid4()),
        type="user_message",
        source="TestTriageAgent",
        data={
            "chat_messages": [{"role": "user"}],
            "connection_id": str(uuid4()),
            "agent": "TriageAgent",
        },
    )

    await handle_user_message(test_message)


@pytest.mark.asyncio
async def test_streaming_edge_cases(monkeypatch):
    """Test edge cases in streaming responses."""
    import dspy

    from agents.triage.agent import human_stream_channel

    load_dotenv()

    mock_publish = AsyncMock()
    monkeypatch.setattr(human_stream_channel, "publish", mock_publish)

    async def mock_chatty_response(*args, **kwargs):
        yield dspy.Prediction(content="test response [[ ## completed ## ]]")

    monkeypatch.setattr(
        "agents.triage.dspy_modules.small_talk.chatty", mock_chatty_response
    )

    test_message = TracedMessage(
        id=str(uuid4()),
        type="user_message",
        source="TestTriageAgent",
        data={
            "chat_messages": [{"role": "user", "content": "hi there"}],
            "connection_id": str(uuid4()),
            "agent": "TriageAgent",
        },
    )

    import agents.triage.agent as triage_module

    mock_response = MockClassifierResponse(
        target_agent=TargetAgent.ChattyAgent, metrics=MockMetrics()
    )

    monkeypatch.setattr(
        triage_module, "current_classifier", lambda **kwargs: mock_response
    )

    await handle_user_message(test_message)

    assert mock_publish.call_count >= 2


def test_classifier_version_imports():
    """Test that main classifier versions can be imported."""
    try:
        from agents.triage.dspy_modules.classifier_v0 import classifier_v0_program

        assert classifier_v0_program is not None
    except ImportError:
        pytest.skip("classifier_v0 not available")

    try:
        from agents.triage.dspy_modules.classifier_v1 import classifier_v1_program

        assert classifier_v1_program is not None
    except ImportError:
        pytest.skip("classifier_v1 not available")

    try:
        from agents.triage.dspy_modules.classifier_v2.classifier_v2 import (
            classifier_v2_program,
        )

        assert classifier_v2_program is not None
    except ImportError:
        pytest.skip("classifier_v2 not available")

    try:
        from agents.triage.dspy_modules.classifier_v4.classifier_v4 import (
            classifier_v4_program,
        )

        assert classifier_v4_program is not None
    except ImportError:
        pytest.skip("classifier_v4 not available")


def test_target_agent_enum():
    """Test TargetAgent enum values."""
    assert TargetAgent.BillingAgent.value == "BillingAgent"
    assert TargetAgent.ClaimsAgent.value == "ClaimsAgent"
    assert TargetAgent.EscalationAgent.value == "EscalationAgent"
    assert TargetAgent.ChattyAgent.value == "ChattyAgent"


@pytest.mark.asyncio
async def test_triage_agent_classification_success(monkeypatch):
    """Test successful classification and routing."""
    load_dotenv()

    from agents.triage.agent import agents_channel

    mock_publish = AsyncMock()
    monkeypatch.setattr(agents_channel, "publish", mock_publish)

    import agents.triage.agent as triage_module

    mock_response = MockClassifierResponse(
        target_agent=TargetAgent.BillingAgent, metrics=MockMetrics()
    )

    monkeypatch.setattr(
        triage_module, "current_classifier", lambda **kwargs: mock_response
    )

    test_message = TracedMessage(
        id=str(uuid4()),
        type="user_message",
        source="TestTriageAgent",
        data={
            "chat_messages": [{"role": "user", "content": "What's my bill?"}],
            "connection_id": str(uuid4()),
            "agent": "TriageAgent",
        },
    )

    await handle_user_message(test_message)

    assert mock_publish.called
    # Check that a routing message was published
    routing_calls = [
        call
        for call in mock_publish.call_args_list
        if call[0][0].type == "billing_request"
    ]
    assert len(routing_calls) > 0


@pytest.mark.asyncio
async def test_triage_agent_claims_routing(monkeypatch):
    """Test routing to claims agent."""
    load_dotenv()

    from agents.triage.agent import agents_channel

    mock_publish = AsyncMock()
    monkeypatch.setattr(agents_channel, "publish", mock_publish)

    import agents.triage.agent as triage_module

    mock_response = MockClassifierResponse(
        target_agent=TargetAgent.ClaimsAgent, metrics=MockMetrics()
    )

    monkeypatch.setattr(
        triage_module, "current_classifier", lambda **kwargs: mock_response
    )

    test_message = TracedMessage(
        id=str(uuid4()),
        type="user_message",
        source="TestTriageAgent",
        data={
            "chat_messages": [{"role": "user", "content": "I need to file a claim"}],
            "connection_id": str(uuid4()),
            "agent": "TriageAgent",
        },
    )

    await handle_user_message(test_message)

    assert mock_publish.called
    # Check that a claims routing message was published
    routing_calls = [
        call
        for call in mock_publish.call_args_list
        if call[0][0].type == "claim_request"
    ]
    assert len(routing_calls) > 0


@pytest.mark.asyncio
async def test_triage_agent_escalation_routing(monkeypatch):
    """Test routing to escalation agent."""
    load_dotenv()

    from agents.triage.agent import agents_channel

    mock_publish = AsyncMock()
    monkeypatch.setattr(agents_channel, "publish", mock_publish)

    import agents.triage.agent as triage_module

    mock_response = MockClassifierResponse(
        target_agent=TargetAgent.EscalationAgent, metrics=MockMetrics()
    )

    monkeypatch.setattr(
        triage_module, "current_classifier", lambda **kwargs: mock_response
    )

    test_message = TracedMessage(
        id=str(uuid4()),
        type="user_message",
        source="TestTriageAgent",
        data={
            "chat_messages": [
                {"role": "user", "content": "I need to speak to a manager"}
            ],
            "connection_id": str(uuid4()),
            "agent": "TriageAgent",
        },
    )

    await handle_user_message(test_message)

    assert mock_publish.called
    # Check that an escalation routing message was published
    routing_calls = [
        call
        for call in mock_publish.call_args_list
        if call[0][0].type == "ticketing_request"
    ]
    assert len(routing_calls) > 0


def test_mock_classes_structure():
    """Test that mock classes have expected structure."""
    metrics = MockMetrics()
    assert hasattr(metrics, "latency_ms")
    assert abs(metrics.latency_ms - 10.5) < 1e-9

    response = MockClassifierResponse(
        target_agent=TargetAgent.BillingAgent, metrics=metrics
    )
    assert hasattr(response, "target_agent")
    assert hasattr(response, "metrics")
    assert response.target_agent == TargetAgent.BillingAgent
