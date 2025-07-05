from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import SettingsConfigDict

from libraries.types import BaseAgentConfig

load_dotenv()


class Settings(BaseAgentConfig):
    app_name: str = Field(default="billing_agent")
    prometheus_metrics_port: int = Field(
        default=9095, description="Port for Prometheus metrics server"
    )
    
    billing_database_path: str = Field(default="")

    model_config = SettingsConfigDict(
        env_prefix="BILLING_", env_file=".env", env_ignore_empty=True, extra="ignore"
    )


settings = Settings()
