from pathlib import Path
from typing import Optional

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
    vespa_config_url: str = Field(default="http://localhost:19071")
    vespa_query_url: str = Field(default="http://localhost:8080")
    
    # Vespa deployment configuration
    vespa_deployment_mode: str = Field(default="production", description="Deployment mode: local or production")
    vespa_node_count: int = Field(default=3, description="Number of nodes for production deployment")
    vespa_artifacts_dir: Optional[Path] = Field(default=None, description="Custom artifacts directory")
    vespa_hosts_config: Optional[Path] = Field(default=None, description="Path to hosts configuration file")
    vespa_services_xml: Optional[Path] = Field(default=None, description="Path to custom services.xml file")

    model_config = SettingsConfigDict(
        env_prefix="POLICIES_DOCUMENT_INGESTION_",
        env_file=".env",
        env_ignore_empty=True,
        extra="ignore",
    )


# Global settings instance
settings = Settings()
