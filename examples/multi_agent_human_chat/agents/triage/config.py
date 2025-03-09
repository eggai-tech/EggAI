from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, model_validator
from typing import Dict, Any
from dotenv import load_dotenv

# Load environment variables at module level
load_dotenv()


class Settings(BaseSettings):
    app_name: str = Field(default="triage_agent", env="APP_NAME")
    
    # Language model settings
    language_model: str = Field(default="openai/gpt-4o-mini", env="LANGUAGE_MODEL")
    cache_enabled: bool = Field(default=False, env="CACHE_ENABLED")
    
    # Kafka transport settings
    kafka_bootstrap_servers: str = Field(default="localhost:19092", env="KAFKA_BOOTSTRAP_SERVERS")
    kafka_topic_prefix: str = Field(default="eggai", env="KAFKA_TOPIC_PREFIX")
    kafka_rebalance_timeout_ms: int = Field(default=20000, env="KAFKA_REBALANCE_TIMEOUT_MS")
    
    # Observability settings
    otel_endpoint: str = Field(default="http://localhost:4318", env="OTEL_ENDPOINT") 
    tracing_enabled: bool = Field(default=True, env="TRACING_ENABLED")
    
    # Agent registry settings
    agent_registry: Dict[str, Dict[str, Any]] = Field(
        default={
            "PoliciesAgent": {
                "message_type": "policy_request",
                "description": "Handles policy-related queries",
            },
            "BillingAgent": {
                "message_type": "billing_request",
                "description": "Handles billing-related queries",
            },
            "TicketingAgent": {
                "message_type": "ticketing_request",
                "description": "Everything related to tickets and support must be handled by this agent",
            },
            "TriageAgent": {
                "message_type": "triage_request",
                "description": "Default agent for handling unclassified requests and smalltalk",
            }
        }
    )
    
    model_config = SettingsConfigDict(
        env_prefix="TRIAGE_", env_file=".env", env_ignore_empty=True, extra="ignore"
    )
    
    @model_validator(mode='after')
    def ensure_triage_agent_in_registry(self) -> 'Settings':
        """Ensures TriageAgent is in the registry for fallback handling."""
        if "TriageAgent" not in self.agent_registry:
            self.agent_registry["TriageAgent"] = {
                "message_type": "triage_request",
                "description": "Default agent for handling unclassified requests and smalltalk",
            }
        return self


settings = Settings()