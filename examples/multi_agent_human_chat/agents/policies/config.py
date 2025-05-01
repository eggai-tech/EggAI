from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
import os
from dotenv import load_dotenv

# Load environment variables at module level
load_dotenv()


class Settings(BaseSettings):
    app_name: str = Field(default="policies_agent", env="APP_NAME")
    
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
    
    # RAG settings
    rag_max_documents: int = Field(default=5, env="RAG_MAX_DOCUMENTS")
    rag_index_path: str = Field(default="", env="RAG_INDEX_PATH")
    
    @property
    def default_rag_index_path(self) -> str:
        if not self.rag_index_path:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            return os.path.join(base_dir, "policies", "rag", ".ragatouille", "colbert", "indexes", "policies_index")
        return self.rag_index_path
    
    model_config = SettingsConfigDict(
        env_prefix="POLICIES_", env_file=".env", env_ignore_empty=True, extra="ignore"
    )


settings = Settings()