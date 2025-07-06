from typing import Dict

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from .types import AuditCategory, AuditConfig

load_dotenv()

MESSAGE_CATEGORIES: Dict[str, AuditCategory] = {
    "agent_message": "User Communication",
    "billing_request": "Billing",
    "policy_request": "Policies",
    "escalation_request": "Escalation",
    "triage_request": "Triage",
}

class Settings(BaseSettings):
    app_name: str = Field(default="audit_agent")
    kafka_bootstrap_servers: str = Field(default="localhost:19092")
    kafka_ca_content: str = Field(default="")
    otel_endpoint: str = Field(default="http://localhost:4318")
    prometheus_metrics_port: int = Field(default=9096)
    
    debug_logging_enabled: bool = Field(default=False)
    audit_channel_name: str = Field(default="audit_logs")
    default_category: AuditCategory = Field(default="Other")

    model_config = SettingsConfigDict(
        env_prefix="AUDIT_", env_file=".env", env_ignore_empty=True, extra="ignore"
    )

settings = Settings()

audit_config = AuditConfig(
    message_categories=MESSAGE_CATEGORIES,
    default_category=settings.default_category,
    enable_debug_logging=settings.debug_logging_enabled,
    audit_channel_name=settings.audit_channel_name,
)
