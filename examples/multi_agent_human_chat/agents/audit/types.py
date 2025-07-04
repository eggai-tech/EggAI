"""Audit agent type definitions."""

from datetime import datetime
from typing import Any, Dict, Literal, Optional

from pydantic import BaseModel, Field

AuditCategory = Literal[
    "User Communication",
    "Billing",
    "Policies",
    "Escalation",
    "Triage",
    "Other",
    "Error",
]

MESSAGE_CATEGORIES: Dict[str, AuditCategory] = {
    "agent_message": "User Communication",
    "billing_request": "Billing",
    "policy_request": "Policies",
    "escalation_request": "Escalation",
    "triage_request": "Triage",
}

__all__ = [
    "AuditCategory",
    "MESSAGE_CATEGORIES",
    "AuditConfig",
    "AuditEvent",
]


class AuditConfig(BaseModel):
    message_categories: Dict[str, AuditCategory] = Field(default_factory=dict)
    default_category: AuditCategory = Field(default="Other")
    enable_debug_logging: bool = Field(default=False)
    audit_channel_name: str = Field(default="audit_logs")

    model_config = {"validate_assignment": True, "extra": "forbid"}


class AuditEvent(BaseModel):
    message_id: str = Field(...)
    message_type: str = Field(...)
    message_source: str = Field(...)
    channel: str = Field(...)
    category: AuditCategory = Field(...)
    audit_timestamp: datetime = Field(default_factory=datetime.now)
    content: Optional[str] = Field(default=None)
    error: Optional[Dict[str, str]] = Field(default=None)

    def to_dict(self) -> Dict[str, Any]:
        result = self.model_dump()
        result["audit_timestamp"] = self.audit_timestamp.isoformat()
        return result

    model_config = {"validate_assignment": True}