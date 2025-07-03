"""Tests for the channels module."""

import pytest

from libraries.channels import ChannelConfig, channels, clear_channels


class TestChannels:
    """Test the Channels configuration class."""

    def test_channels_initialization(self):
        """Test that channels object has all required attributes."""
        # channels is already instantiated in the module
        
        # Verify all channel attributes exist
        assert hasattr(channels, "agents")
        assert hasattr(channels, "human")
        assert hasattr(channels, "human_stream")
        assert hasattr(channels, "audit_logs")
        assert hasattr(channels, "metrics")
        assert hasattr(channels, "debug")
        
        # Verify channel names
        assert channels.agents == "agents"
        assert channels.human == "human"
        assert channels.human_stream == "human_stream"
        assert channels.audit_logs == "audit_logs"

    def test_channel_config_class(self):
        """Test that ChannelConfig can be instantiated."""
        config = ChannelConfig()
        
        # Verify default values
        assert config.agents == "agents"
        assert config.human == "human"
        assert config.human_stream == "human_stream"
        assert config.audit_logs == "audit_logs"

    def test_channels_are_strings(self):
        """Test that all channel names are strings."""
        assert isinstance(channels.agents, str)
        assert isinstance(channels.human, str)
        assert isinstance(channels.human_stream, str)
        assert isinstance(channels.audit_logs, str)

    @pytest.mark.asyncio
    async def test_clear_channels_import(self):
        """Test that clear_channels is importable and callable."""
        # This just verifies the function exists and is callable
        assert callable(clear_channels)
        
        # We can't test the actual clearing without a real Kafka setup,
        # but we can verify it doesn't crash when called
        try:
            result = await clear_channels()
            # The function might return None or some status
            assert result is None or isinstance(result, (bool, dict, list))
        except Exception as e:
            # If it requires actual Kafka connection, it might fail
            # but that's expected in unit tests
            assert "kafka" in str(e).lower() or "connection" in str(e).lower()


    def test_channel_names_are_not_empty(self):
        """Test that channel names are not empty."""
        assert len(channels.agents) > 0
        assert len(channels.human) > 0
        assert len(channels.human_stream) > 0
        assert len(channels.audit_logs) > 0

    def test_channel_names_are_unique(self):
        """Test that all channel names are unique."""
        channel_names = [
            channels.agents,
            channels.human,
            channels.human_stream,
            channels.audit_logs,
            channels.metrics,
            channels.debug
        ]
        
        # Convert to set to check uniqueness
        assert len(channel_names) == len(set(channel_names))

    def test_channels_module_exports(self):
        """Test that the module exports the expected items."""
        import libraries.channels as channels_module
        
        # Verify module exports
        assert hasattr(channels_module, "ChannelConfig")
        assert hasattr(channels_module, "channels")
        assert hasattr(channels_module, "clear_channels")
        
        # Verify channels is an instance of ChannelConfig
        assert isinstance(channels_module.channels, ChannelConfig)


class TestChannelsIntegration:
    """Integration tests for channels with mocked dependencies."""

    def test_channels_usage_pattern(self):
        """Test the typical usage pattern of channels."""
        from libraries.channels import channels
        
        # Simulate how channels are used in the codebase
        agent_channel = channels.agents
        human_channel = channels.human
        
        # Verify we can use these as channel names
        assert isinstance(agent_channel, str)
        assert isinstance(human_channel, str)
        
        # Simulate passing to a messaging system
        mock_publish_data = {
            "channel": agent_channel,
            "message": "test message"
        }
        
        assert mock_publish_data["channel"] == "agents"

    def test_channels_in_different_contexts(self):
        """Test channels work correctly in different contexts."""
        from libraries.channels import channels
        
        # Test in agent context
        class MockAgent:
            def __init__(self):
                self.channel = channels.agents
        
        agent = MockAgent()
        assert agent.channel == "agents"
        
        # Test in service context
        class MockService:
            def __init__(self):
                self.human_channel = channels.human
                self.stream_channel = channels.human_stream
        
        service = MockService()
        assert service.human_channel == "human"
        assert service.stream_channel == "human_stream"