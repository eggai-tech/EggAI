"""Configuration settings for the Audit Agent."""

from typing import Optional

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

load_dotenv()


class Settings(BaseSettings):
    app_name: str = Field(default="audit_agent")

    # Language model settings (not directly used but kept for compatibility)
    language_model: str = Field(default="openai/gpt-4o-mini")
    language_model_api_base: Optional[str] = Field(default=None)
    cache_enabled: bool = Field(default=False)
    max_context_window: Optional[int] = Field(default=None)

    # Kafka transport settings
    kafka_bootstrap_servers: str = Field(default="localhost:19092")
    kafka_topic_prefix: str = Field(default="eggai")
    kafka_rebalance_timeout_ms: int = Field(default=20000)
    kafka_ca_content: str = Field(default="")

    # Observability settings
    otel_endpoint: str = Field(default="http://localhost:4318")
    tracing_enabled: bool = Field(default=True)
    debug_logging_enabled: bool = Field(default=False)
    prometheus_metrics_port: int = Field(
        default=9096, description="Port for Prometheus metrics server"
    )

    # Audit specific settings
    audit_channel_name: str = Field(default="audit_logs")

    model_config = SettingsConfigDict(
        env_prefix="AUDIT_", env_file=".env", env_ignore_empty=True, extra="ignore"
    )


settings = Settings()
