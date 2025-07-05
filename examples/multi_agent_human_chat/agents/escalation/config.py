
from pydantic import Field
from pydantic_settings import SettingsConfigDict

from libraries.types import BaseAgentConfig


class Settings(BaseAgentConfig):

    app_name: str = Field(default="escalation_agent")
    prometheus_metrics_port: int = Field(default=9094, description="Port for Prometheus metrics server")

    ticket_database_path: str = Field(default="")
    default_departments: list[str] = Field(default=["Technical Support", "Billing", "Sales"])
    timeout_seconds: float = Field(default=30.0, description="Timeout for model inference in seconds")

    model_config = SettingsConfigDict(
        env_prefix="ESCALATION_", env_file=".env", env_ignore_empty=True, extra="ignore"
    )


settings = Settings()
