import os

from pydantic import Field
from pydantic_settings import SettingsConfigDict

from libraries.core import BaseAgentConfig


class Settings(BaseAgentConfig):
    app_name: str = Field(default="frontend_agent")
    prometheus_metrics_port: int = Field(default=9097, description="Port for Prometheus metrics server")
    
    host: str = Field(default="127.0.0.1")
    port: int = Field(default=8000)
    log_level: str = Field(default="info")
    
    websocket_path: str = Field(default="/ws")
    websocket_ping_interval: float = Field(default=30.0)
    websocket_ping_timeout: float = Field(default=10.0)

    public_dir: str = Field(default="")

    @property
    def default_public_dir(self) -> str:
        if not self.public_dir:
            return os.path.join(os.path.dirname(os.path.abspath(__file__)), "public")
        return self.public_dir

    model_config = SettingsConfigDict(
        env_prefix="FRONTEND_", env_file=".env", env_ignore_empty=True, extra="ignore"
    )


settings = Settings()
