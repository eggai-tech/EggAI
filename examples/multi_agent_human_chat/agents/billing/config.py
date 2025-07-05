from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import SettingsConfigDict

from libraries.types import BaseAgentConfig

from .types import BillingModelConfig

load_dotenv()

MESSAGE_TYPE_BILLING_REQUEST = "billing_request"


class Settings(BaseAgentConfig):
    app_name: str = Field(default="billing_agent")
    prometheus_metrics_port: int = Field(
        default=9095, description="Port for Prometheus metrics server"
    )
    
    billing_database_path: str = Field(default="")
    
    model_name: str = Field(default="billing_react", description="Name of the model")
    max_iterations: int = Field(default=5, ge=1, le=10)
    use_tracing: bool = Field(default=True)
    cache_enabled: bool = Field(default=False)
    timeout_seconds: float = Field(default=30.0, ge=1.0)
    truncation_length: int = Field(default=15000, ge=1000)

    model_config = SettingsConfigDict(
        env_prefix="BILLING_", env_file=".env", env_ignore_empty=True, extra="ignore"
    )


settings = Settings()

model_config = BillingModelConfig(
    name=settings.model_name,
    max_iterations=settings.max_iterations,
    use_tracing=settings.use_tracing,
    cache_enabled=settings.cache_enabled,
    timeout_seconds=settings.timeout_seconds,
    truncation_length=settings.truncation_length,
)
