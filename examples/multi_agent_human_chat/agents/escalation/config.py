from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import SettingsConfigDict

from libraries.types import BaseAgentConfig

from .types import DspyModelConfig

load_dotenv()

AGENT_NAME = "TicketingAgent"
MSG_TYPE_TICKETING_REQUEST = "ticketing_request"
MSG_TYPE_STREAM_START = "agent_message_stream_start"
MSG_TYPE_STREAM_CHUNK = "agent_message_stream_chunk"
MSG_TYPE_STREAM_END = "agent_message_stream_end"
GROUP_ID = "escalation_agent_group"


class Settings(BaseAgentConfig):
    app_name: str = Field(default="escalation_agent")
    prometheus_metrics_port: int = Field(default=9094, description="Port for Prometheus metrics server")

    ticket_database_path: str = Field(default="")
    default_departments: list[str] = Field(default=["Technical Support", "Billing", "Sales"])
    
    model_name: str = Field(default="ticketing_react", description="Name of the model")
    max_iterations: int = Field(default=5, ge=1, le=10)
    use_tracing: bool = Field(default=True)
    cache_enabled: bool = Field(default=False)  
    timeout_seconds: float = Field(default=30.0, description="Timeout for model inference in seconds")
    truncation_length: int = Field(default=15000, ge=1000)

    model_config = SettingsConfigDict(
        env_prefix="ESCALATION_", env_file=".env", env_ignore_empty=True, extra="ignore"
    )


settings = Settings()

dspy_model_config = DspyModelConfig(
    name=settings.model_name,
    max_iterations=settings.max_iterations,
    use_tracing=settings.use_tracing,
    cache_enabled=settings.cache_enabled,
    timeout_seconds=settings.timeout_seconds,
    truncation_length=settings.truncation_length,
)
