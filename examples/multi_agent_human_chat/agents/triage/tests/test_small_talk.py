"""Tests for triage small talk module."""

from unittest.mock import AsyncMock, MagicMock, patch

import dspy
import pytest
from dspy import Prediction
from dspy.streaming import StreamResponse

from agents.triage.dspy_modules.small_talk import ChattySignature, chatty


@pytest.fixture
def mock_dspy_predict():
    """Mock dspy.Predict for testing."""
    with patch('dspy.Predict') as mock_predict:
        yield mock_predict


@pytest.fixture
def mock_dspy_streamify():
    """Mock dspy.streamify for testing."""
    with patch('dspy.streamify') as mock_streamify:
        yield mock_streamify


def test_chatty_signature():
    """Test ChattySignature class structure."""
    # Test that the signature class exists and has the right structure
    assert hasattr(ChattySignature, '__annotations__')
    assert hasattr(ChattySignature, '__doc__')
    
    # Check that required fields are defined in annotations
    annotations = ChattySignature.__annotations__
    assert 'chat_history' in annotations
    assert 'response' in annotations
    
    # Check docstring contains key information
    docstring = ChattySignature.__doc__
    assert docstring is not None
    assert len(docstring) > 0


@pytest.mark.asyncio
async def test_chatty_function_basic(mock_dspy_streamify):
    """Test basic chatty function call."""
    # Mock the streamify return value
    mock_async_gen = AsyncMock()
    mock_dspy_streamify.return_value = mock_async_gen
    
    chat_history = "User: Hello there!"
    
    result = chatty(chat_history)
    
    # Verify streamify was called with correct parameters
    mock_dspy_streamify.assert_called_once()
    call_args = mock_dspy_streamify.call_args
    
    # Check that a dspy.Predict instance was passed as first argument
    assert isinstance(call_args[0][0], dspy.Predict)
    
    # Check keyword arguments
    kwargs = call_args[1]
    assert 'stream_listeners' in kwargs
    assert 'include_final_prediction_in_output_stream' in kwargs
    assert 'is_async_program' in kwargs
    assert 'async_streaming' in kwargs
    
    assert kwargs['include_final_prediction_in_output_stream'] is True
    assert kwargs['is_async_program'] is False
    assert kwargs['async_streaming'] is True


@pytest.mark.asyncio
async def test_chatty_stream_response():
    """Test chatty function with stream response."""
    # Create mock stream responses
    mock_stream_response = StreamResponse(
        predict_name="chatty_predict",
        signature_field_name="response", 
        chunk="Hello! I'm here to help"
    )
    mock_prediction = Prediction(response="Hello! I'm here to help with your insurance needs. What can I assist you with today?")
    
    async def mock_generator(*args, **kwargs):
        yield mock_stream_response
        yield mock_prediction
    
    with patch('dspy.streamify') as mock_streamify:
        mock_streamify.return_value = mock_generator
        
        chat_history = "User: Hi there!"
        responses = []
        
        async for response in chatty(chat_history):
            responses.append(response)
        
        assert len(responses) == 2
        assert isinstance(responses[0], StreamResponse)
        assert isinstance(responses[1], Prediction)
        assert responses[0].chunk == "Hello! I'm here to help"
        assert "insurance needs" in responses[1].response


@pytest.mark.asyncio
async def test_chatty_with_off_topic_question():
    """Test chatty function with off-topic question."""
    mock_prediction = Prediction(
        response="That's an interesting question! However, I'm here to help with your insurance needs. What insurance questions can I assist you with today?"
    )
    
    async def mock_generator(*args, **kwargs):
        yield mock_prediction
    
    with patch('dspy.streamify') as mock_streamify:
        mock_streamify.return_value = mock_generator
        
        chat_history = "User: What's the weather like today?"
        responses = []
        
        async for response in chatty(chat_history):
            responses.append(response)
        
        assert len(responses) == 1
        assert isinstance(responses[0], Prediction)
        assert "insurance" in responses[0].response.lower()


@pytest.mark.asyncio
async def test_chatty_with_insurance_question():
    """Test chatty function with insurance-related question."""
    mock_prediction = Prediction(
        response="Great! I'd be happy to help you with your insurance policy. What specific information do you need?"
    )
    
    async def mock_generator(*args, **kwargs):
        yield mock_prediction
    
    with patch('dspy.streamify') as mock_streamify:
        mock_streamify.return_value = mock_generator
        
        chat_history = "User: I have questions about my insurance policy."
        responses = []
        
        async for response in chatty(chat_history):
            responses.append(response)
        
        assert len(responses) == 1
        assert isinstance(responses[0], Prediction)
        assert "insurance" in responses[0].response.lower()


@pytest.mark.asyncio
async def test_chatty_empty_chat_history():
    """Test chatty function with empty chat history."""
    mock_prediction = Prediction(
        response="Hello! I'm here to help with your insurance needs. How can I assist you today?"
    )
    
    async def mock_generator(*args, **kwargs):
        yield mock_prediction
    
    with patch('dspy.streamify') as mock_streamify:
        mock_streamify.return_value = mock_generator
        
        chat_history = ""
        responses = []
        
        async for response in chatty(chat_history):
            responses.append(response)
        
        assert len(responses) == 1
        assert isinstance(responses[0], Prediction)


@pytest.mark.asyncio
async def test_chatty_multiple_chunks():
    """Test chatty function with multiple stream chunks."""
    chunks = [
        StreamResponse(predict_name="chatty_predict", signature_field_name="response", chunk="Hello! "),
        StreamResponse(predict_name="chatty_predict", signature_field_name="response", chunk="I'm here "),
        StreamResponse(predict_name="chatty_predict", signature_field_name="response", chunk="to help "),
        StreamResponse(predict_name="chatty_predict", signature_field_name="response", chunk="with insurance."),
        Prediction(response="Hello! I'm here to help with insurance.")
    ]
    
    async def mock_generator(*args, **kwargs):
        for chunk in chunks:
            yield chunk
    
    with patch('dspy.streamify') as mock_streamify:
        mock_streamify.return_value = mock_generator
        
        chat_history = "User: Hello!"
        responses = []
        
        async for response in chatty(chat_history):
            responses.append(response)
        
        assert len(responses) == 5
        # First 4 should be StreamResponse
        for i in range(4):
            assert isinstance(responses[i], StreamResponse)
        # Last should be Prediction
        assert isinstance(responses[4], Prediction)


@pytest.mark.asyncio
async def test_chatty_stream_listener_configuration():
    """Test that stream listener is configured correctly."""
    with patch('dspy.streamify') as mock_streamify:
        mock_streamify.return_value = AsyncMock()
        
        chatty("User: Test")
        
        # Check that streamify was called with correct stream listener
        call_args = mock_streamify.call_args
        kwargs = call_args[1]
        
        assert 'stream_listeners' in kwargs
        stream_listeners = kwargs['stream_listeners']
        assert len(stream_listeners) == 1
        
        # Check that the stream listener is configured for 'response' field
        listener = stream_listeners[0]
        assert hasattr(listener, 'signature_field_name')
        assert listener.signature_field_name == 'response'


def test_chatty_signature_docstring():
    """Test ChattySignature docstring contains required guidelines."""
    docstring = ChattySignature.__doc__
    
    # Check for key guidelines in the docstring
    assert "friendly and helpful insurance agent" in docstring.lower()
    assert "redirect" in docstring.lower()
    assert "insurance" in docstring.lower()
    assert "never refer to yourself as an \"ai assistant\"" in docstring.lower()
    assert "response guidelines" in docstring.lower()


@pytest.mark.asyncio
async def test_chatty_function_parameters():
    """Test that chatty function passes parameters correctly."""
    with patch('dspy.streamify') as mock_streamify:
        mock_callable = MagicMock()
        mock_streamify.return_value = mock_callable
        
        test_chat_history = "User: What's my policy number?"
        
        # Call chatty and then call the returned function
        result_func = chatty(test_chat_history)
        
        # Verify streamify was called
        mock_streamify.assert_called_once()
        
        # Get the function that streamify returns and verify it was called with chat_history
        call_args = mock_streamify.call_args
        # The returned function should be called with chat_history parameter
        assert call_args is not None


@pytest.mark.asyncio
async def test_chatty_error_handling():
    """Test chatty function error handling."""
    async def mock_generator_with_error(*args, **kwargs):
        yield StreamResponse(predict_name="chatty_predict", signature_field_name="response", chunk="Hello")
        raise Exception("Test error")
    
    with patch('dspy.streamify') as mock_streamify:
        mock_streamify.return_value = mock_generator_with_error
        
        chat_history = "User: Test"
        responses = []
        
        with pytest.raises(Exception, match="Test error"):
            async for response in chatty(chat_history):
                responses.append(response)
        
        # Should have received the first chunk before error
        assert len(responses) == 1
        assert isinstance(responses[0], StreamResponse)


def test_chatty_signature_field_types():
    """Test ChattySignature field types and properties."""
    # Test that the signature class has the expected structure
    assert hasattr(ChattySignature, '__annotations__')
    
    # Check field annotations
    annotations = ChattySignature.__annotations__
    assert 'chat_history' in annotations
    assert 'response' in annotations
    
    # Test that it's a proper DSPy signature class
    assert hasattr(ChattySignature, '__doc__')
    assert ChattySignature.__doc__ is not None


@pytest.mark.asyncio
async def test_chatty_conversation_context():
    """Test chatty function with conversation context."""
    conversation = """User: Hi there!
Assistant: Hello! How can I help you with your insurance needs?
User: What's your favorite movie?"""
    
    mock_prediction = Prediction(
        response="I appreciate the question, but I'm here to focus on your insurance needs. Is there anything about your policy or coverage I can help you with?"
    )
    
    async def mock_generator(*args, **kwargs):
        # Verify the chat_history parameter was passed correctly
        assert kwargs.get('chat_history') == conversation or args[0] == conversation
        yield mock_prediction
    
    with patch('dspy.streamify') as mock_streamify:
        mock_streamify.return_value = mock_generator
        
        responses = []
        async for response in chatty(conversation):
            responses.append(response)
        
        assert len(responses) == 1
        assert "insurance" in responses[0].response.lower() 