from typing import Optional

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import SettingsConfigDict

from libraries.core import BaseAgentConfig

load_dotenv()

MESSAGE_TYPE_USER_MESSAGE = "user_message"
GROUP_ID = "triage_agent_group"


class Settings(BaseAgentConfig):
    app_name: str = Field(default="triage_agent")

    language_model: str = Field(default="openai/gpt-4o-mini")
    language_model_api_base: Optional[str] = Field(default=None)
    cache_enabled: bool = Field(default=False)

    kafka_bootstrap_servers: str = Field(default="localhost:19092")
    kafka_topic_prefix: str = Field(default="eggai")
    kafka_rebalance_timeout_ms: int = Field(default=20000)
    kafka_ca_content: str = Field(default="")

    otel_endpoint: str = Field(default="http://localhost:4318")
    tracing_enabled: bool = Field(default=True)
    prometheus_metrics_port: int = Field(default=9091, description="Port for Prometheus metrics server")

    classifier_version: str = Field(default="v2")
    classifier_v3_model_name: str = Field(default="fewshot_classifier_n_200")
    classifier_v3_model_version: str = Field(default="1")

    classifier_v5_model_name: str = Field(default="attention_net_0.25_0.0002")
    classifier_v5_model_version: str = Field(default="1")
    classifier_v5_device: str = Field(default="cuda")

    classifier_v6_model_id: Optional[str] = Field(default=None, description="Fine-tuned OpenAI model ID for classifier v6")

    copro_dataset_size: int = Field(default=50)
    bootstrap_dataset_size: int = Field(default=30)
    copro_breadth: int = Field(default=10)
    copro_depth: int = Field(default=3)

    test_dataset_size: int = Field(default=10)

    model_config = SettingsConfigDict(
        env_prefix="TRIAGE_", env_file=".env", env_ignore_empty=True, extra="ignore"
    )


settings = Settings()
