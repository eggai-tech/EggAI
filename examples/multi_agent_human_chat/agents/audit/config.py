from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from dotenv import load_dotenv

load_dotenv()


class Settings(BaseSettings):
    app_name: str = Field(default="audit_agent", env="APP_NAME")
    kafka_bootstrap_servers: str = Field(default="localhost:19092", env="KAFKA_BOOTSTRAP_SERVERS")
    kafka_topic_prefix: str = Field(default="eggai", env="KAFKA_TOPIC_PREFIX")
    kafka_rebalance_timeout_ms: int = Field(default=20000, env="KAFKA_REBALANCE_TIMEOUT_MS")
    otel_endpoint: str = Field(default="http://localhost:4318", env="OTEL_ENDPOINT") 
    tracing_enabled: bool = Field(default=True, env="TRACING_ENABLED")
    model_config = SettingsConfigDict(
        env_prefix="AUDIT_", env_file=".env", env_ignore_empty=True, extra="ignore"
    )


settings = Settings()