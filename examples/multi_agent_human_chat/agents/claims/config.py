from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from dotenv import load_dotenv

# Load environment variables at module level
load_dotenv()


class Settings(BaseSettings):
    app_name: str = Field(default="claims_agent")

    # Language model settings
    language_model: str = Field(default="openai/gpt-4o-mini")
    language_model_api_base: Optional[str] = Field(default=None)
    cache_enabled: bool = Field(default=False)

    # Kafka transport settings
    kafka_bootstrap_servers: str = Field(default="localhost:19092")
    kafka_topic_prefix: str = Field(default="eggai")
    kafka_rebalance_timeout_ms: int = Field(default=20000)
    kafka_ca_content: str = Field(default="")

    # Observability settings
    otel_endpoint: str = Field(default="http://localhost:4318")
    tracing_enabled: bool = Field(default=True)

    # Claims specific settings
    claims_database_path: str = Field(default="")

    model_config = SettingsConfigDict(
        env_prefix="CLAIMS_", env_file=".env", env_ignore_empty=True, extra="ignore"
    )


settings = Settings()
