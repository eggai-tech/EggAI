from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from dotenv import load_dotenv

load_dotenv()


class Settings(BaseSettings):
    app_name: str = Field(default="triage_agent")
    
    # Language model settings
    language_model: str = Field(default="openai/gpt-4o-mini")
    language_model_api_base: Optional[str] = Field(default=None)
    cache_enabled: bool = Field(default=False)
    
    # Kafka transport settings
    kafka_bootstrap_servers: str = Field(default="localhost:19092")
    kafka_topic_prefix: str = Field(default="eggai")
    kafka_rebalance_timeout_ms: int = Field(default=20000)
    kafka_ca_content: str = Field(default="")
    
    # Observability settings
    otel_endpoint: str = Field(default="http://localhost:4318") 
    tracing_enabled: bool = Field(default=True)

    # Classifier settings
    classifier_version: str = Field(default="v2")
    classifier_v3_model_name: str = Field(default="fewshot_classifier_n_200")
    classifier_v3_model_version: str = Field(default="1")
    
    # COPRO optimizer settings for classifier_v4
    copro_dataset_size: int = Field(default=100)
    copro_breadth: int = Field(default=10)
    copro_depth: int = Field(default=3)
    
    # Testing settings
    test_dataset_size: int = Field(default=10)  # Limit number of test examples for quicker comparison
    
    model_config = SettingsConfigDict(
        env_prefix="TRIAGE_", env_file=".env", env_ignore_empty=True, extra="ignore"
    )


settings = Settings()