import os
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
    
    # Deployment configuration
    deployment_namespace: Optional[str] = Field(
        default=None,
        description="Namespace for deployment (e.g., pr-123, staging, prod)"
    )

    # Temporal configuration
    temporal_server_url: str = Field(default="localhost:7233")
    temporal_namespace: Optional[str] = Field(
        default=None, 
        description="Temporal namespace (uses deployment_namespace if not set)"
    )
    temporal_task_queue_base: str = Field(
        default="policy-rag",
        description="Base task queue name (will be prefixed with namespace if provided)"
    )

    # OpenTelemetry configuration
    otel_endpoint: str = Field(default="http://localhost:4318")

    # Vespa configuration
    vespa_config_url: str = Field(default="http://localhost:19071")
    vespa_query_url: str = Field(default="http://localhost:8080")
    vespa_app_name_base: str = Field(
        default="policies",
        description="Base Vespa app name (will be prefixed with namespace if provided)"
    )
    
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
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # If deployment namespace not set in POLICIES_DOCUMENT_INGESTION_ vars, check DEPLOYMENT_NAMESPACE
        if not self.deployment_namespace:
            self.deployment_namespace = os.getenv("DEPLOYMENT_NAMESPACE")
    
    def get_temporal_namespace(self) -> str:
        """Get the Temporal namespace, using deployment namespace as fallback."""
        if self.temporal_namespace:
            return self.temporal_namespace
        if self.deployment_namespace:
            return self.deployment_namespace
        return "default"
    
    @property
    def temporal_task_queue(self) -> str:
        """Get the Temporal task queue with namespace prefix if configured."""
        if self.deployment_namespace:
            return f"{self.deployment_namespace}-{self.temporal_task_queue_base}"
        return self.temporal_task_queue_base
    
    @property
    def vespa_app_name(self) -> str:
        """Get the Vespa app name with namespace prefix if configured."""
        if self.deployment_namespace:
            return f"{self.deployment_namespace}-{self.vespa_app_name_base}"
        return self.vespa_app_name_base


# Global settings instance
settings = Settings()
