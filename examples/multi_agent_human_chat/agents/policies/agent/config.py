from typing import Optional

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import SettingsConfigDict

from libraries.types import BaseAgentConfig

from .types import ModelConfig

load_dotenv()

AGENT_NAME = "Policies"
CONSUMER_GROUP_ID = "policies_agent_group"
MESSAGE_TYPE_POLICY_REQUEST = "policy_request"
MESSAGE_TYPE_AGENT_MESSAGE = "agent_message"
MESSAGE_TYPE_STREAM_CHUNK = "agent_message_stream_chunk"
MESSAGE_TYPE_STREAM_END = "agent_message_stream_end"


class Settings(BaseAgentConfig):
    app_name: str = Field(default="policies_agent")
    prometheus_metrics_port: int = Field(default=9093, description="Port for Prometheus metrics server")
    
    max_context_window: Optional[int] = Field(default=None)
    embedding_model: str = Field(default="all-MiniLM-L6-v2", description="Sentence transformer model for embeddings")
    api_port: int = Field(default=8002, description="Port for the Policies API")
    api_host: str = Field(default="0.0.0.0", description="Host for the Policies API")
    
    model_name: str = Field(default="policies_react", description="Name of the model")
    max_iterations: int = Field(default=5, ge=1, le=10)
    use_tracing: bool = Field(default=True)
    cache_enabled: bool = Field(default=False)
    timeout_seconds: float = Field(default=30.0, ge=1.0)
    truncation_length: int = Field(default=15000, ge=1000)

    model_config = SettingsConfigDict(
        env_prefix="POLICIES_", env_file=".env", env_ignore_empty=True, extra="ignore"
    )


settings = Settings()

model_config = ModelConfig(
    name=settings.model_name,
    max_iterations=settings.max_iterations,
    use_tracing=settings.use_tracing,
    cache_enabled=settings.cache_enabled,
    timeout_seconds=settings.timeout_seconds,
    truncation_length=settings.truncation_length,
)
