import os
from typing import Optional

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Load environment variables at module level
load_dotenv()


class Settings(BaseSettings):
    app_name: str = Field(default="policies_agent")

    # Language model settings
    language_model: str = Field(default="openai/gpt-4o-mini")
    language_model_api_base: Optional[str] = Field(default=None)
    cache_enabled: bool = Field(default=False)
    max_context_window: Optional[int] = Field(
        default=None
    )  # Set to None to use provider defaults

    # Kafka transport settings
    kafka_bootstrap_servers: str = Field(default="localhost:19092")
    kafka_topic_prefix: str = Field(default="eggai")
    kafka_rebalance_timeout_ms: int = Field(default=20000)
    kafka_ca_content: str = Field(default="")

    # Observability settings
    otel_endpoint: str = Field(default="http://localhost:4318")
    tracing_enabled: bool = Field(default=True)
    prometheus_metrics_port: int = Field(
        default=9093, description="Port for Prometheus metrics server"
    )

    # RAG settings
    rag_max_documents: int = Field(default=5)
    rag_index_path: str = Field(default="")

    @property
    def default_rag_index_path(self) -> str:
        if not self.rag_index_path:
            # Navigate from agents/policies to repo root
            base_dir = os.path.dirname(os.path.abspath(__file__))
            repo_root = os.path.dirname(os.path.dirname(base_dir))
            return os.path.join(
                repo_root,
                ".cache",
                "colbert",
                "indexes",
                "policies_index",
            )
        return self.rag_index_path

    model_config = SettingsConfigDict(
        env_prefix="POLICIES_", env_file=".env", env_ignore_empty=True, extra="ignore"
    )


settings = Settings()
