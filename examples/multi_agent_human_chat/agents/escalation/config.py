from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from dotenv import load_dotenv

# Load environment variables at module level
load_dotenv()


class Settings(BaseSettings):
    app_name: str = Field(default="escalation_agent", env="APP_NAME")
    
    # Language model settings
    language_model: str = Field(default="openai/gpt-4o-mini", env="LANGUAGE_MODEL")
    language_model_api_base: Optional[str] = Field(default=None, env="LANGUAGE_MODEL_API_BASE")
    cache_enabled: bool = Field(default=False, env="CACHE_ENABLED")
    
    # Kafka transport settings
    kafka_bootstrap_servers: str = Field(default="localhost:19092", env="KAFKA_BOOTSTRAP_SERVERS")
    kafka_topic_prefix: str = Field(default="eggai", env="KAFKA_TOPIC_PREFIX")
    kafka_rebalance_timeout_ms: int = Field(default=20000, env="KAFKA_REBALANCE_TIMEOUT_MS")
    
    # Observability settings
    otel_endpoint: str = Field(default="http://localhost:4318", env="OTEL_ENDPOINT") 
    tracing_enabled: bool = Field(default=True, env="TRACING_ENABLED")
    
    # Ticketing specific settings
    ticket_database_path: str = Field(default="", env="TICKET_DATABASE_PATH")
    default_departments: list[str] = Field(
        default=["Technical Support", "Billing", "Sales"],
        env="DEFAULT_DEPARTMENTS"
    )
    
    model_config = SettingsConfigDict(
        env_prefix="ESCALATION_", env_file=".env", env_ignore_empty=True, extra="ignore"
    )


settings = Settings()