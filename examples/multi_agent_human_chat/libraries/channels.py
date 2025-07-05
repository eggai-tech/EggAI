import os
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ChannelConfig(BaseSettings):
    """Configuration for channel names used throughout the system.
    
    Supports deployment namespacing via DEPLOYMENT_NAMESPACE env var
    to allow multiple deployments on the same infrastructure.
    """
    
    # Deployment namespace (e.g., "pr-123", "staging", "prod")
    deployment_namespace: Optional[str] = Field(
        default=None,
        description="Namespace prefix for all channels (e.g., pr-123, staging)"
    )
    
    # Base channel names (will be prefixed with namespace if provided)
    agents_base: str = Field(
        default="agents", description="Base name for inter-agent communication channel"
    )
    human_base: str = Field(
        default="human", description="Base name for human-agent communication channel"
    )
    human_stream_base: str = Field(
        default="human_stream",
        description="Base name for streaming human-agent communication channel",
    )
    audit_logs_base: str = Field(
        default="audit_logs", description="Base name for audit logging channel"
    )
    metrics_base: str = Field(
        default="metrics", description="Base name for metrics and telemetry channel"
    )
    debug_base: str = Field(
        default="debug", description="Base name for debug information channel"
    )

    model_config = SettingsConfigDict(
        env_prefix="CHANNEL_", env_file=".env", env_ignore_empty=True, extra="ignore"
    )
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # If deployment namespace not set in CHANNEL_ vars, check DEPLOYMENT_NAMESPACE
        if not self.deployment_namespace:
            self.deployment_namespace = os.getenv("DEPLOYMENT_NAMESPACE")
    
    def _apply_namespace(self, base_name: str) -> str:
        """Apply deployment namespace to channel name if configured."""
        if self.deployment_namespace:
            return f"{self.deployment_namespace}-{base_name}"
        return base_name
    
    @property
    def agents(self) -> str:
        return self._apply_namespace(self.agents_base)
    
    @property
    def human(self) -> str:
        return self._apply_namespace(self.human_base)
    
    @property
    def human_stream(self) -> str:
        return self._apply_namespace(self.human_stream_base)
    
    @property
    def audit_logs(self) -> str:
        return self._apply_namespace(self.audit_logs_base)
    
    @property
    def metrics(self) -> str:
        return self._apply_namespace(self.metrics_base)
    
    @property
    def debug(self) -> str:
        return self._apply_namespace(self.debug_base)


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
            ]
        )
    except Exception as e:
        print(f"Error deleting topics: {e}")
    finally:
        await admin.close()


if __name__ == "__main__":
    import asyncio

    asyncio.run(clear_channels())
