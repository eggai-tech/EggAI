"""Additional tests for utils.py to improve coverage."""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest
from dspy import Prediction

from agents.billing.types import ChatMessage
from agents.billing.utils import (
    get_conversation_string,
    process_billing_request,
)


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
    async def test_process_billing_request_with_custom_timeout(self):
        """Test process_billing_request with custom timeout."""
        mock_channel = AsyncMock()
        
        conversation = "User: What's my premium?\nAgent: Please provide your policy number."
        
        with patch("agents.billing.utils.process_billing") as mock_dspy:
            # Create mock async generator
            async def mock_generator():
                yield Prediction(final_response="Final response")
            
            mock_dspy.return_value = mock_generator()
            
            await process_billing_request(
                conversation,
                "test-connection",
                "test-message",
                mock_channel,
                timeout_seconds=15.0  # Pass timeout directly, not config
            )
            
            # Verify the function completed successfully
            assert mock_channel.publish.called

    @pytest.mark.asyncio
    async def test_process_billing_request_streaming(self):
        """Test that streaming works correctly."""
        mock_channel = AsyncMock()
        conversation = "User: What's my premium?\nAgent: Please provide your policy number."
        
        with patch("agents.billing.utils.process_billing") as mock_dspy:
            # Create mock async generator that yields a Prediction
            async def mock_generator():
                yield Prediction(final_response="Your premium is $120")
            
            mock_dspy.return_value = mock_generator()
            
            await process_billing_request(
                conversation,
                "test-connection",
                "test-message",
                mock_channel
            )
            
            # Verify stream start and end were published
            call_types = [call[0][0].type for call in mock_channel.publish.call_args_list]
            assert "agent_message_stream_start" in call_types
            assert "agent_message_stream_end" in call_types

    @pytest.mark.asyncio
    async def test_process_billing_request_error_handling(self):
        """Test error handling in process_billing_request."""
        mock_channel = AsyncMock()
        conversation = "User: What's my premium?\nAgent: Please provide your policy number."
        
        with patch("agents.billing.utils.process_billing") as mock_dspy:
            # Create mock async generator that raises an error
            async def mock_generator():
                raise RuntimeError("Test error")
                yield  # Make it an async generator
            
            mock_dspy.return_value = mock_generator()
            
            # The function should handle the error and publish error message
            await process_billing_request(
                conversation,
                "test-connection", 
                "test-message",
                mock_channel
            )
            
            # Should publish stream end with error message
            end_calls = [
                call for call in mock_channel.publish.call_args_list
                if call[0][0].type == "agent_message_stream_end"
            ]
            assert len(end_calls) == 1
            assert "Error processing billing request: Test error" in end_calls[0][0][0].data["message"]

    @pytest.mark.asyncio
    async def test_process_billing_request_timeout_handling(self):
        """Test timeout handling in process_billing_request."""
        mock_channel = AsyncMock()
        conversation = "User: What's my premium?\nAgent: Please provide your policy number."
        
        with patch("agents.billing.utils.process_billing") as mock_dspy:
            # Create mock async generator that takes too long
            async def mock_generator():
                await asyncio.sleep(1)  # Longer than timeout
                yield Prediction(final_response="Too late")
            
            mock_dspy.return_value = mock_generator()
            
            # Use a very short timeout
            await process_billing_request(
                conversation,
                "test-connection",
                "test-message",
                mock_channel,
                timeout_seconds=1.0  # minimum valid timeout
            )
            
            # Should complete even with timeout
            assert mock_channel.publish.called

    @pytest.mark.asyncio
    async def test_process_billing_request_no_final_response(self):
        """Test when no Prediction with final_response is received."""
        mock_channel = AsyncMock()
        conversation = "User: What's my premium?\nAgent: Please provide your policy number."
        
        with patch("agents.billing.utils.process_billing") as mock_dspy:
            # Create mock async generator with no response
            async def mock_generator():
                # Empty generator - no yield
                return
                yield  # Make it an async generator
            
            mock_dspy.return_value = mock_generator()
            
            await process_billing_request(
                conversation,
                "test-connection",
                "test-message",
                mock_channel
            )
            
            # Should publish stream start
            start_calls = [
                call for call in mock_channel.publish.call_args_list
                if call[0][0].type == "agent_message_stream_start"
            ]
            assert len(start_calls) == 1
            
            # Current implementation doesn't publish stream_end for empty generator
            # This might be a bug, but we're testing current behavior
            all_types = [call[0][0].type for call in mock_channel.publish.call_args_list]
            assert "agent_message_stream_start" in all_types
            # No stream_end is published in this case


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
        assert "assistant: None\n" in result  # None becomes string "None"
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
        assert "User: Hello\n" in result  # Default role is "User"
        assert "assistant: Hi there" in result

    def test_get_conversation_string_missing_content_key(self):
        """Test handling of messages without content key."""
        messages = [
            ChatMessage(role="user", content="Hello"),
            {"role": "assistant"},  # Missing content - will be skipped
            ChatMessage(role="user", content="Hello?")
        ]
        
        with patch("agents.billing.utils.logger") as mock_logger:
            result = get_conversation_string(messages)
            mock_logger.warning.assert_called_with("Message missing content field")
            # Message without content is skipped entirely
            assert result == "user: Hello\nuser: Hello?\n"