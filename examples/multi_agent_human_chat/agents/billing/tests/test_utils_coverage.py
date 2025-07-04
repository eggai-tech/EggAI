"""Additional tests for utils.py to improve coverage."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from dspy import Prediction
from dspy.streaming import StreamResponse

from agents.billing.types import ChatMessage, ModelConfig
from agents.billing.utils import (
    get_conversation_string,
    process_billing_request,
)
from libraries.tracing import TracedMessage


class TestProcessBillingRequest:
    """Test process_billing_request function with various scenarios."""

    @pytest.mark.asyncio
    async def test_process_billing_request_empty_conversation(self):
        """Test process_billing_request with empty conversation."""
        mock_channel = AsyncMock()
        
        with pytest.raises(ValueError, match="Conversation history is too short"):
            await process_billing_request(
                "",
                "test-connection",
                "test-message",
                mock_channel
            )
        
        # Should publish stream start before raising
        mock_channel.publish.assert_called()

    @pytest.mark.asyncio
    async def test_process_billing_request_very_short_conversation(self):
        """Test process_billing_request with very short conversation."""
        mock_channel = AsyncMock()
        
        with pytest.raises(ValueError, match="Conversation history is too short"):
            await process_billing_request(
                "Hi",  # Less than 5 characters
                "test-connection",
                "test-message",
                mock_channel
            )

    @pytest.mark.asyncio
    async def test_process_billing_request_with_custom_config(self):
        """Test process_billing_request with custom ModelConfig."""
        mock_channel = AsyncMock()
        config = ModelConfig(timeout_seconds=10)
        
        conversation = "User: What's my premium?\nAgent: Please provide your policy number."
        
        with patch("agents.billing.utils.billing_optimized_dspy") as mock_dspy:
            # Create mock async generator
            async def mock_generator():
                yield StreamResponse(chunk="Test response")
                yield Prediction(final_response="Final response")
            
            mock_dspy.return_value = mock_generator()
            
            await process_billing_request(
                conversation,
                "test-connection",
                "test-message",
                mock_channel,
                config
            )
            
            # Verify custom config was passed
            mock_dspy.assert_called_once()
            call_args = mock_dspy.call_args
            assert call_args[1]["config"] == config

    @pytest.mark.asyncio
    async def test_process_billing_request_chunk_counting(self):
        """Test that chunks are counted correctly."""
        mock_channel = AsyncMock()
        conversation = "User: What's my premium?\nAgent: Please provide your policy number."
        
        with patch("agents.billing.utils.billing_optimized_dspy") as mock_dspy:
            # Create mock async generator with multiple chunks
            async def mock_generator():
                yield StreamResponse(chunk="Chunk 1")
                yield StreamResponse(chunk="Chunk 2")
                yield StreamResponse(chunk="Chunk 3")
                yield Prediction(final_response="Final response")
            
            mock_dspy.return_value = mock_generator()
            
            await process_billing_request(
                conversation,
                "test-connection",
                "test-message",
                mock_channel
            )
            
            # Count how many chunk messages were published
            chunk_calls = [
                call for call in mock_channel.publish.call_args_list
                if call[0][0].type == "agent_message_stream_chunk"
            ]
            assert len(chunk_calls) == 3
            
            # Verify chunk indices
            for i, call in enumerate(chunk_calls):
                assert call[0][0].data["chunk_index"] == i + 1

    @pytest.mark.asyncio
    async def test_process_billing_request_error_handling(self):
        """Test error handling in process_billing_request."""
        mock_channel = AsyncMock()
        conversation = "User: What's my premium?\nAgent: Please provide your policy number."
        
        with patch("agents.billing.utils.billing_optimized_dspy") as mock_dspy:
            # Create mock async generator that raises an error
            async def mock_generator():
                yield StreamResponse(chunk="Start")
                raise RuntimeError("Test error")
            
            mock_dspy.return_value = mock_generator()
            
            with pytest.raises(RuntimeError, match="Test error"):
                await process_billing_request(
                    conversation,
                    "test-connection",
                    "test-message",
                    mock_channel
                )
            
            # Should still publish error message
            error_calls = [
                call for call in mock_channel.publish.call_args_list
                if call[0][0].type == "agent_message_stream_error"
            ]
            assert len(error_calls) == 1

    @pytest.mark.asyncio
    async def test_process_billing_request_timeout_handling(self):
        """Test timeout handling in process_billing_request."""
        mock_channel = AsyncMock()
        config = ModelConfig(timeout_seconds=0.1)  # Very short timeout
        conversation = "User: What's my premium?\nAgent: Please provide your policy number."
        
        with patch("agents.billing.utils.billing_optimized_dspy") as mock_dspy:
            # Create mock async generator that takes too long
            async def mock_generator():
                await asyncio.sleep(1)  # Longer than timeout
                yield StreamResponse(chunk="Too late")
            
            mock_dspy.return_value = mock_generator()
            
            with pytest.raises(asyncio.TimeoutError):
                await process_billing_request(
                    conversation,
                    "test-connection",
                    "test-message",
                    mock_channel,
                    config
                )

    @pytest.mark.asyncio
    async def test_process_billing_request_no_final_response(self):
        """Test when no Prediction with final_response is received."""
        mock_channel = AsyncMock()
        conversation = "User: What's my premium?\nAgent: Please provide your policy number."
        
        with patch("agents.billing.utils.billing_optimized_dspy") as mock_dspy:
            # Create mock async generator with only chunks, no final response
            async def mock_generator():
                yield StreamResponse(chunk="Chunk 1")
                yield StreamResponse(chunk="Chunk 2")
                # No Prediction yielded
            
            mock_dspy.return_value = mock_generator()
            
            await process_billing_request(
                conversation,
                "test-connection",
                "test-message",
                mock_channel
            )
            
            # Should still complete without error
            # Check that stream end was published
            end_calls = [
                call for call in mock_channel.publish.call_args_list
                if call[0][0].type == "agent_message_stream_end"
            ]
            assert len(end_calls) == 1
            assert end_calls[0][0][0].data["message"] == ""  # Empty message


class TestGetConversationString:
    """Test get_conversation_string function edge cases."""

    def test_get_conversation_string_with_none_content(self):
        """Test handling of None content in messages."""
        messages = [
            ChatMessage(role="user", content="Hello"),
            ChatMessage(role="assistant", content=None),  # None content
            ChatMessage(role="user", content="Are you there?")
        ]
        
        result = get_conversation_string(messages)
        assert "user: Hello\n" in result
        assert "assistant: \n" in result  # None becomes empty string
        assert "user: Are you there?" in result

    def test_get_conversation_string_with_special_characters(self):
        """Test handling of special characters in conversation."""
        messages = [
            ChatMessage(role="user", content="What's the status of policy #A12345?"),
            ChatMessage(role="assistant", content="Your premium is $120.50 & due on 01/15")
        ]
        
        result = get_conversation_string(messages)
        assert "#A12345" in result
        assert "$120.50 & due" in result

    def test_get_conversation_string_with_multiline_content(self):
        """Test handling of multiline messages."""
        messages = [
            ChatMessage(role="user", content="Hello,\nI have multiple questions:\n1. Premium\n2. Due date"),
            ChatMessage(role="assistant", content="Sure!\nLet me help you.")
        ]
        
        result = get_conversation_string(messages)
        assert "Hello,\nI have multiple questions:\n1. Premium\n2. Due date" in result

    def test_get_conversation_string_empty_list(self):
        """Test with empty message list."""
        result = get_conversation_string([])
        assert result == ""

    def test_get_conversation_string_missing_role(self):
        """Test handling of messages with missing role."""
        messages = [
            {"content": "Hello"},  # Missing role
            ChatMessage(role="assistant", content="Hi there")
        ]
        
        result = get_conversation_string(messages)
        assert "Unknown: Hello\n" in result
        assert "assistant: Hi there" in result

    def test_get_conversation_string_missing_content_key(self):
        """Test handling of messages without content key."""
        messages = [
            ChatMessage(role="user", content="Hello"),
            {"role": "assistant"},  # Missing content
            ChatMessage(role="user", content="Hello?")
        ]
        
        with patch("agents.billing.utils.logger") as mock_logger:
            result = get_conversation_string(messages)
            mock_logger.warning.assert_called_with("Message missing content field")
            assert "assistant: \n" in result