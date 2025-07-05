from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import SettingsConfigDict

from libraries.types import BaseAgentConfig

from .types import ClaimsModelConfig

load_dotenv()

MESSAGE_TYPE_CLAIM_REQUEST = "claim_request"


class Settings(BaseAgentConfig):
    app_name: str = Field(default="claims_agent")
    prometheus_metrics_port: int = Field(default=9092)
    
    model_name: str = Field(default="claims_react", description="Name of the model")
    max_iterations: int = Field(default=5, ge=1, le=10)
    use_tracing: bool = Field(default=True)
    cache_enabled: bool = Field(default=False)
    timeout_seconds: float = Field(default=30.0, ge=1.0)
    truncation_length: int = Field(default=15000, ge=1000)

    model_config = SettingsConfigDict(
        env_prefix="CLAIMS_", env_file=".env", env_ignore_empty=True, extra="ignore"
    )


settings = Settings()

model_config = ClaimsModelConfig(
    name=settings.model_name,
    max_iterations=settings.max_iterations,
    use_tracing=settings.use_tracing,
    cache_enabled=settings.cache_enabled,
    timeout_seconds=settings.timeout_seconds,
    truncation_length=settings.truncation_length,
)
