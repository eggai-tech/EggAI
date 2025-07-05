from pydantic import Field
from pydantic_settings import SettingsConfigDict

from libraries.types import BaseAgentConfig


class Settings(BaseAgentConfig):
    app_name: str = Field(default="claims_agent")
    prometheus_metrics_port: int = Field(default=9092)


    model_config = SettingsConfigDict(
        env_prefix="CLAIMS_", env_file=".env", env_ignore_empty=True, extra="ignore"
    )


settings = Settings()
