from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
import os
from dotenv import load_dotenv

# Load environment variables at module level
load_dotenv()


class Settings(BaseSettings):
    app_name: str = Field(default="frontend_agent", env="APP_NAME")
    
    # Server settings
    host: str = Field(default="127.0.0.1", env="HOST")
    port: int = Field(default=8000, env="PORT")
    log_level: str = Field(default="info", env="LOG_LEVEL")
    
    # Websocket settings
    websocket_path: str = Field(default="/ws", env="WEBSOCKET_PATH")
    websocket_ping_interval: float = Field(default=30.0, env="WEBSOCKET_PING_INTERVAL")
    websocket_ping_timeout: float = Field(default=10.0, env="WEBSOCKET_PING_TIMEOUT")
    
    # Kafka transport settings
    kafka_bootstrap_servers: str = Field(default="localhost:19092", env="KAFKA_BOOTSTRAP_SERVERS")
    kafka_topic_prefix: str = Field(default="eggai", env="KAFKA_TOPIC_PREFIX")
    kafka_rebalance_timeout_ms: int = Field(default=20000, env="KAFKA_REBALANCE_TIMEOUT_MS")
    
    # Observability settings
    otel_endpoint: str = Field(default="http://localhost:4318", env="OTEL_ENDPOINT") 
    tracing_enabled: bool = Field(default=True, env="TRACING_ENABLED")
    
    # Static files
    public_dir: str = Field(default="", env="PUBLIC_DIR")
    
    @property
    def default_public_dir(self) -> str:
        if not self.public_dir:
            return os.path.join(os.path.dirname(os.path.abspath(__file__)), "public")
        return self.public_dir
    
    model_config = SettingsConfigDict(
        env_prefix="FRONTEND_", env_file=".env", env_ignore_empty=True, extra="ignore"
    )


settings = Settings()