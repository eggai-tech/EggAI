from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class BaseAgentConfig(BaseSettings):
    # Core settings - must be provided by each agent
    app_name: str = Field(
        ...,
        description="Unique application name for the agent"
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
    
    # Base configuration - to be overridden by each agent
    model_config = SettingsConfigDict(
        env_file=".env",
        env_ignore_empty=True,
        extra="ignore"
    )