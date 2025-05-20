from typing import Optional

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

load_dotenv()


class Settings(BaseSettings):
    app_name: str = Field(default="react_agent")

    # Language model settings
    language_model: str = Field(default="openai/gpt-4o-mini")
    language_model_api_base: Optional[str] = Field(default=None)
    cache_enabled: bool = Field(default=False)

    model_config = SettingsConfigDict(
        env_prefix="REACT_AGENT_",
        env_file=".env",
        env_ignore_empty=True,
        extra="ignore",
    )


settings = Settings()
