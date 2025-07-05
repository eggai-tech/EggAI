import os
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class VespaConfig(BaseSettings):
    """Configuration settings for Vespa integration."""
    
    # Deployment configuration
    deployment_namespace: Optional[str] = Field(
        default=None,
        description="Namespace for deployment (e.g., pr-123, staging, prod)"
    )

    # Vespa connection settings
    vespa_url: str = Field(default="http://localhost:8080")
    vespa_app_name_base: str = Field(
        default="policies", 
        description="Base Vespa app name (will be prefixed with namespace if provided)"
    )
    vespa_timeout: int = Field(default=120)
    vespa_connections: int = Field(default=5)

    # Schema settings
    schema_name: str = Field(default="policy_document")

    # Indexing settings
    batch_size: int = Field(default=100)
    max_retries: int = Field(default=3)

    # Query settings
    max_hits: int = Field(default=10)
    ranking_profile: str = Field(default="default")

    model_config = SettingsConfigDict(
        env_prefix="VESPA_", env_file=".env", env_ignore_empty=True, extra="ignore"
    )
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # If deployment namespace not set in VESPA_ vars, check DEPLOYMENT_NAMESPACE
        if not self.deployment_namespace:
            self.deployment_namespace = os.getenv("DEPLOYMENT_NAMESPACE")
    
    @property
    def vespa_app_name(self) -> str:
        """Get the Vespa app name with namespace prefix if configured."""
        if self.deployment_namespace:
            return f"{self.deployment_namespace}-{self.vespa_app_name_base}"
        return self.vespa_app_name_base


vespa_config = VespaConfig()
