"""Configuration settings for the Audit Agent."""
__all__ = [
    "Settings",
    "settings",
]


from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

load_dotenv()


class Settings(BaseSettings):
    app_name: str = Field(default="audit_agent")

    # Kafka transport settings
    kafka_bootstrap_servers: str = Field(default="localhost:19092")
    kafka_ca_content: str = Field(default="")

    # Observability settings
    otel_endpoint: str = Field(default="http://localhost:4318")
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
