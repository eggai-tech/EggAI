"""Tests for test fixtures and setup functions to improve coverage."""

import pytest
from unittest.mock import MagicMock, patch
from eggai import Agent, Channel

from agents.billing.tests.test_agent import setup_kafka_transport, test_components


class TestKafkaTransportFixture:
    """Test the Kafka transport fixture."""

    def test_setup_kafka_transport_fixture(self):
        """Test that setup_kafka_transport properly configures transport."""
        with patch("agents.billing.tests.test_agent.eggai_set_default_transport") as mock_set_transport:
            with patch("agents.billing.tests.test_agent.create_kafka_transport") as mock_create_transport:
                mock_transport = MagicMock()
                mock_create_transport.return_value = mock_transport
                
                # Use the fixture
                gen = setup_kafka_transport()
                next(gen)  # Execute up to yield
                
                # Verify transport was set
                mock_set_transport.assert_called_once()
                mock_create_transport.assert_called_once()
                
                # Test cleanup (after yield)
                try:
                    next(gen)
                except StopIteration:
                    pass


class TestComponentsFixture:
    """Test the test_components fixture."""

    def test_test_components_fixture_creation(self):
        """Test that test_components creates all required components."""
        # Mock the kafka transport fixture
        mock_kafka_fixture = MagicMock()
        
        with patch("agents.billing.tests.test_agent.Agent") as mock_agent_class:
            with patch("agents.billing.tests.test_agent.Channel") as mock_channel_class:
                with patch("agents.billing.tests.test_agent.dspy_set_language_model") as mock_dspy:
                    with patch("agents.billing.agent.billing_agent") as mock_billing_agent:
                        # Set up mocks
                        mock_test_agent = MagicMock(spec=Agent)
                        mock_agent_class.return_value = mock_test_agent
                        mock_channel = MagicMock(spec=Channel)
                        mock_channel_class.return_value = mock_channel
                        mock_dspy_lm = MagicMock()
                        mock_dspy.return_value = mock_dspy_lm
                        
                        # Execute fixture
                        components = test_components(mock_kafka_fixture)
                        
                        # Verify all components are present
                        assert "billing_agent" in components
                        assert "test_agent" in components
                        assert "test_channel" in components
                        assert "human_channel" in components
                        assert "human_stream_channel" in components
                        assert "response_queue" in components
                        assert "dspy_lm" in components
                        
                        # Verify agent was created with correct name
                        mock_agent_class.assert_called_once_with("TestBillingAgent")
                        
                        # Verify channels were created
                        assert mock_channel_class.call_count == 3  # Three channels created

    def test_test_components_response_handler_registration(self):
        """Test that response handler is properly registered."""
        mock_kafka_fixture = MagicMock()
        
        with patch("agents.billing.tests.test_agent.Agent") as mock_agent_class:
            with patch("agents.billing.tests.test_agent.Channel"):
                with patch("agents.billing.tests.test_agent.dspy_set_language_model"):
                    with patch("agents.billing.agent.billing_agent"):
                        # Set up mock agent with subscribe method
                        mock_test_agent = MagicMock(spec=Agent)
                        mock_subscribe_decorator = MagicMock()
                        mock_test_agent.subscribe = MagicMock(return_value=mock_subscribe_decorator)
                        mock_agent_class.return_value = mock_test_agent
                        
                        # Execute fixture
                        test_components(mock_kafka_fixture)
                        
                        # Verify subscribe was called with correct parameters
                        mock_test_agent.subscribe.assert_called_once()
                        call_kwargs = mock_test_agent.subscribe.call_args[1]
                        
                        # Check filter function
                        filter_func = call_kwargs["filter_by_message"]
                        assert filter_func({"type": "agent_message_stream_end"}) is True
                        assert filter_func({"type": "other_type"}) is False
                        
                        # Check other parameters
                        assert call_kwargs["auto_offset_reset"] == "latest"
                        assert call_kwargs["group_id"] == "test_billing_agent_group"