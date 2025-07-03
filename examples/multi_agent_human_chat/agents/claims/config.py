from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = Field(default="claims_agent")

    # Language model settings
    language_model: str = Field(default="openai/gpt-4o-mini")
    language_model_api_base: Optional[str] = Field(default=None)
    cache_enabled: bool = Field(default=False)

    # Kafka transport settings (used by create_kafka_transport)
    kafka_bootstrap_servers: str = Field(default="localhost:19092")
    kafka_ca_content: str = Field(default="")

    # Observability settings
    otel_endpoint: str = Field(default="http://localhost:4318")
    tracing_enabled: bool = Field(default=True)
    prometheus_metrics_port: int = Field(
        default=9092, description="Port for Prometheus metrics server"
    )


    model_config = SettingsConfigDict(
        env_prefix="CLAIMS_", env_file=".env", env_ignore_empty=True, extra="ignore"
    )


settings = Settings()
