"""
Channel name configuration for the EggAI multi-agent system.

This module defines the standard channel names used for communication between agents.
Using this centralized configuration helps maintain consistency and makes changes easier.
"""
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ChannelConfig(BaseSettings):
    """Configuration for channel names used throughout the system."""
    
    # Main agent communication channels
    agents: str = Field(default="agents", description="Channel for inter-agent communication")
    human: str = Field(default="human", description="Channel for human-agent communication")
    audit_logs: str = Field(default="audit_logs", description="Channel for audit logging")
    
    # For potential future use
    metrics: str = Field(default="metrics", description="Channel for metrics and telemetry")
    debug: str = Field(default="debug", description="Channel for debug information")
    
    model_config = SettingsConfigDict(
        env_prefix="CHANNEL_", env_file=".env", env_ignore_empty=True, extra="ignore"
    )


# Create a singleton instance to be imported by other modules
channels = ChannelConfig()