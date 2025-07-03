from typing import Optional

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

load_dotenv()


class Settings(BaseSettings):
    app_name: str = Field(default="billing_agent")

    # Language model settings
    language_model: str = Field(default="openai/gpt-4o-mini")
    language_model_api_base: Optional[str] = Field(default=None)
    cache_enabled: bool = Field(default=False)

    # Kafka transport settings
    kafka_bootstrap_servers: str = Field(default="localhost:19092")
    kafka_ca_content: str = Field(default="")

    # Observability settings
    otel_endpoint: str = Field(default="http://localhost:4318")
    prometheus_metrics_port: int = Field(
        default=9095, description="Port for Prometheus metrics server"
    )


    model_config = SettingsConfigDict(
        env_prefix="BILLING_", env_file=".env", env_ignore_empty=True, extra="ignore"
    )


settings = Settings()
