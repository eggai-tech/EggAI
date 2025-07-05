from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class BaseAgentConfig(BaseSettings):
    # Core settings - must be provided by each agent
    app_name: str = Field(
        ...,
        description="Unique application name for the agent"
    )
    
    # Deployment configuration
    deployment_namespace: Optional[str] = Field(
        default=None,
        description="Namespace for deployment (e.g., pr-123, staging, prod)"
    )
    
    # Language model settings
    language_model: str = Field(
        default="openai/gpt-4o-mini",
        description="Language model to use for agent reasoning"
    )
    language_model_api_base: Optional[str] = Field(
        default=None,
        description="Optional API base URL for the language model"
    )
    cache_enabled: bool = Field(
        default=False,
        description="Whether to enable model result caching"
    )
    
    # Kafka settings
    kafka_bootstrap_servers: str = Field(
        default="localhost:19092",
        description="Kafka bootstrap servers for message transport"
    )
    kafka_ca_content: str = Field(
        default="",
        description="Kafka CA certificate content for SSL connections"
    )
    kafka_topic_prefix: str = Field(
        default="eggai",
        description="Prefix for Kafka topics"
    )
    kafka_rebalance_timeout_ms: int = Field(
        default=20000,
        description="Kafka consumer rebalance timeout in milliseconds"
    )
    
    # Observability settings
    otel_endpoint: str = Field(
        default="http://localhost:4318",
        description="OpenTelemetry collector endpoint"
    )
    tracing_enabled: bool = Field(
        default=True,
        description="Whether to enable distributed tracing"
    )
    prometheus_metrics_port: int = Field(
        ...,
        description="Port for Prometheus metrics endpoint (must be unique per agent)"
    )
    
    # Temporal configuration (for agents that use it)
    temporal_namespace: Optional[str] = Field(
        default=None,
        description="Temporal namespace (uses deployment_namespace if not set)"
    )
    temporal_task_queue: Optional[str] = Field(
        default=None,
        description="Temporal task queue (uses agent-specific default if not set)"
    )
    
    # Base configuration - to be overridden by each agent
    model_config = SettingsConfigDict(
        env_file=".env",
        env_ignore_empty=True,
        extra="ignore"
    )
    
    def get_temporal_namespace(self) -> str:
        """Get the Temporal namespace, using deployment namespace as fallback."""
        if self.temporal_namespace:
            return self.temporal_namespace
        if self.deployment_namespace:
            return self.deployment_namespace
        return "default"
    
    def get_temporal_task_queue(self, default_queue: str) -> str:
        """Get the Temporal task queue with deployment namespace prefix if configured."""
        base_queue = self.temporal_task_queue or default_queue
        if self.deployment_namespace:
            return f"{self.deployment_namespace}-{base_queue}"
        return base_queue