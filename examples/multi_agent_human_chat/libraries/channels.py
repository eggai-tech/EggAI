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
    agents: str = Field(
        default="agents", description="Channel for inter-agent communication"
    )
    human: str = Field(
        default="human", description="Channel for human-agent communication"
    )
    human_stream: str = Field(
        default="human_stream",
        description="Channel for streaming human-agent communication",
    )
    audit_logs: str = Field(
        default="audit_logs", description="Channel for audit logging"
    )
    internal: str = Field(
        default="internal", description="Channel for internal agent communication"
    )

    # For potential future use
    metrics: str = Field(
        default="metrics", description="Channel for metrics and telemetry"
    )
    debug: str = Field(default="debug", description="Channel for debug information")

    model_config = SettingsConfigDict(
        env_prefix="CHANNEL_", env_file=".env", env_ignore_empty=True, extra="ignore"
    )


channels = ChannelConfig()


# using FastStream empty topics
async def clear_channels():
    from aiokafka.admin import AIOKafkaAdminClient

    from agents.triage.config import Settings

    settings = Settings()
    admin = AIOKafkaAdminClient(bootstrap_servers=settings.kafka_bootstrap_servers)

    await admin.start()

    try:
        await admin.delete_topics(
            [
                channels.human,
                channels.human_stream,
                channels.agents,
                channels.audit_logs,
                channels.internal,
            ]
        )
    except Exception as e:
        print(f"Error deleting topics: {e}")
    finally:
        await admin.close()


if __name__ == "__main__":
    import asyncio

    asyncio.run(clear_channels())
