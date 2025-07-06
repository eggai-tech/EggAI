from unittest.mock import MagicMock, patch

import pytest

from agents.escalation.dspy_modules.escalation import (
    TicketingSignature,
    process_escalation,
)


@pytest.fixture
def mock_dspy_react():
    """Mock dspy.ReAct for testing."""
    with patch("dspy.ReAct") as mock_react:
        yield mock_react


@pytest.fixture
def mock_escalation_tools():
    """Mock escalation tools for testing."""
    with (
        patch(
            "agents.escalation.dspy_modules.escalation.get_tickets_by_policy"
        ) as mock_get_tickets,
        patch(
            "agents.escalation.dspy_modules.escalation.create_ticket"
        ) as mock_create_ticket,
    ):
        yield mock_get_tickets, mock_create_ticket


def test_ticketing_signature():
    """Test TicketingSignature class structure."""
    # Test that the signature class exists and has the right structure
    assert hasattr(TicketingSignature, "__annotations__")
    assert hasattr(TicketingSignature, "__doc__")

    # Check that required fields are defined in annotations
    annotations = TicketingSignature.__annotations__
    assert "chat_history" in annotations
    assert "final_response" in annotations

    # Check docstring contains key information
    docstring = TicketingSignature.__doc__
    assert docstring is not None
    assert len(docstring) > 0


@pytest.mark.asyncio
async def test_escalation_optimized_dspy_basic():
    """Test basic process_escalation function call."""
    chat_history = "User: I need to speak to a manager about my policy."

    # Mock the ReAct response
    mock_response = MagicMock()
    mock_response.final_response = (
        "I'll create a ticket for you to speak with a manager."
    )

    async def mock_generator(*args, **kwargs):
        yield mock_response

    with patch(
        "agents.escalation.dspy_modules.escalation.escalation_model"
    ) as mock_escalation:
        with patch("dspy.streamify") as mock_streamify:
            mock_streamify.return_value = mock_generator

            responses = []
            async for response in process_escalation(chat_history):
                responses.append(response)

            assert len(responses) == 1
            assert (
                responses[0].final_response
                == "I'll create a ticket for you to speak with a manager."
            )


@pytest.mark.asyncio
async def test_escalation_optimized_dspy_empty_chat():
    """Test escalation function with empty chat history."""
    chat_history = ""

    mock_response = MagicMock()
    mock_response.final_response = "How can I help you with your escalation needs?"

    async def mock_generator(*args, **kwargs):
        yield mock_response

    with patch("dspy.streamify") as mock_streamify:
        mock_streamify.return_value = mock_generator

        responses = []
        async for response in process_escalation(chat_history):
            responses.append(response)

        assert len(responses) == 1
        assert isinstance(responses[0].final_response, str)


@pytest.mark.asyncio
async def test_escalation_optimized_dspy_error_handling():
    """Test escalation function error handling."""
    chat_history = "User: Test error handling"

    async def mock_generator_with_error(*args, **kwargs):
        yield MagicMock(final_response="Starting to help...")
        raise Exception("Test error")

    with patch("dspy.streamify") as mock_streamify:
        mock_streamify.return_value = mock_generator_with_error

        responses = []
        with pytest.raises(Exception, match="Test error"):
            async for response in process_escalation(chat_history):
                responses.append(response)

        # Should have received the first response before error
        assert len(responses) == 1
        assert "Starting to help" in responses[0].final_response


def test_ticketing_signature_docstring():
    """Test TicketingSignature docstring contains required information."""
    docstring = TicketingSignature.__doc__

    # Check for key elements in the docstring
    assert "escalation agent" in docstring.lower()
    assert "ticket" in docstring.lower()
    assert "policy" in docstring.lower()


@pytest.mark.asyncio
async def test_escalation_optimized_dspy_conversation_context():
    """Test escalation function with conversation context."""
    conversation = """User: Hi, I've been trying to resolve an issue with my claim.
TicketingAgent: I can help you with that. What seems to be the problem?
User: My claim has been pending for weeks without any update."""

    mock_response = MagicMock()
    mock_response.final_response = (
        "I've created an urgent escalation ticket T004 for your pending claim."
    )

    async def mock_generator(*args, **kwargs):
        # Verify the chat_history parameter was passed correctly
        assert len(args) > 0 or "chat_history" in kwargs
        yield mock_response

    with patch("dspy.streamify") as mock_streamify:
        mock_streamify.return_value = mock_generator

        responses = []
        async for response in process_escalation(conversation):
            responses.append(response)

        assert len(responses) == 1
        assert "ticket" in responses[0].final_response.lower()


def test_ticketing_signature_field_types():
    """Test TicketingSignature field types and properties."""
    # Test that the signature class has the expected structure
    assert hasattr(TicketingSignature, "__annotations__")

    # Check field annotations
    annotations = TicketingSignature.__annotations__
    assert "chat_history" in annotations
    assert "final_response" in annotations

    # Test that it's a proper DSPy signature class
    assert hasattr(TicketingSignature, "__doc__")
    assert TicketingSignature.__doc__ is not None


def test_escalation_module_imports():
    """Test that escalation module imports work correctly."""
    # Test that we can import the main components
    from agents.escalation.dspy_modules.escalation import (
        TicketingSignature,
        create_ticket,
        get_tickets_by_policy,
        process_escalation,
    )

    # Test that functions exist
    assert callable(process_escalation)
    assert callable(get_tickets_by_policy)
    assert callable(create_ticket)

    # Test that signature class exists
    assert TicketingSignature is not None


@pytest.mark.asyncio
async def test_escalation_optimized_dspy_with_config():
    """Test escalation function with custom config."""
    from agents.escalation.types import ModelConfig

    chat_history = "User: Test with config"
    config = ModelConfig(name="test_model", max_iterations=3)

    mock_response = MagicMock()
    mock_response.final_response = "Response with custom config"

    async def mock_generator(*args, **kwargs):
        yield mock_response

    with patch("dspy.streamify") as mock_streamify:
        mock_streamify.return_value = mock_generator

        responses = []
        async for response in process_escalation(chat_history, config):
            responses.append(response)

        assert len(responses) == 1
        assert "custom config" in responses[0].final_response.lower()
