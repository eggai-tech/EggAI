from typing import Optional

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import SettingsConfigDict

from libraries.types import BaseAgentConfig

load_dotenv()


class Settings(BaseAgentConfig):
    app_name: str = Field(default="policies_agent")
    prometheus_metrics_port: int = Field(default=9093, description="Port for Prometheus metrics server")
    
    # Agent-specific configuration
    max_context_window: Optional[int] = Field(default=None)
    embedding_model: str = Field(default="all-MiniLM-L6-v2", description="Sentence transformer model for embeddings")
    api_port: int = Field(default=8002, description="Port for the Policies API")
    api_host: str = Field(default="0.0.0.0", description="Host for the Policies API")

    model_config = SettingsConfigDict(
        env_prefix="POLICIES_", env_file=".env", env_ignore_empty=True, extra="ignore"
    )


settings = Settings()
