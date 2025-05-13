"""Type definitions for the Audit Agent."""
from datetime import datetime
from typing import Any, Dict, Literal, Optional, TypedDict

from pydantic import BaseModel, Field

AuditCategory = Literal["User Communication", "Billing", "Policies", "Escalation", "Triage", "Other", "Error"]


class ChatMessage(TypedDict, total=False):
    content: str
    role: str


class MessageData(TypedDict, total=False):
    message_id: str
    message_type: str
    message_source: str
    channel: str
    category: AuditCategory
    audit_timestamp: str
    error: Optional[Dict[str, str]]


class AuditLogMessage(TypedDict):
    id: str
    type: Literal["audit_log"]
    source: Literal["AuditAgent"]
    data: MessageData
    traceparent: Optional[str]
    tracestate: Optional[str]


class TracedMessageDict(TypedDict, total=False):
    id: str
    type: str
    source: str
    data: Dict[str, Any]
    traceparent: Optional[str]
    tracestate: Optional[str]


class AuditConfig(BaseModel):
    message_categories: Dict[str, AuditCategory] = Field(
        default_factory=dict,
        description="Mapping of message types to audit categories"
    )
    default_category: AuditCategory = Field(
        default="Other",
        description="Default category for messages without a specific mapping"
    )
    enable_debug_logging: bool = Field(
        default=False,
        description="Whether to enable debug logging for audited messages"
    )
    audit_channel_name: str = Field(
        default="audit_logs",
        description="Channel name for audit log messages"
    )
    
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