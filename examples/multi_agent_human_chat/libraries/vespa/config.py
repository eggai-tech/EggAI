"""Vespa configuration settings."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class VespaConfig(BaseSettings):
    """Configuration settings for Vespa integration."""

    # Vespa connection settings
    vespa_url: str = Field(default="http://localhost:8080")
    vespa_app_name: str = Field(default="policies")
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


vespa_config = VespaConfig()
