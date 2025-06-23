from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Load environment variables at module level
load_dotenv()


class Settings(BaseSettings):
    """Settings for the policies document ingestion service."""

    app_name: str = Field(default="policies_document_ingestion")
    
    # Temporal configuration
    temporal_server_url: str = Field(default="localhost:7233")
    temporal_namespace: str = Field(default="default")
    temporal_task_queue: str = Field(default="policy-rag")
    
    # OpenTelemetry configuration
    otel_endpoint: str = Field(default="http://localhost:4318")
    
    # Vespa configuration
    vespa_host: str = Field(default="localhost")
    vespa_port: int = Field(default=8080)

    model_config = SettingsConfigDict(
        env_prefix="POLICIES_DOCUMENT_INGESTION_",
        env_file=".env",
        env_ignore_empty=True,
        extra="ignore"
    )


# Global settings instance
settings = Settings() 