"""
EggAI Message Protocol

This package contains the shared message protocol definitions used across all agents.
In a distributed setup, this could be extracted to a separate package.
"""

from .enums import AgentName, AuditCategory, MessageType, OffsetReset
from .messages import (
    AgentMessage,
    # Request/Response data
    AgentRequestData,
    AgentResponseData,
    AuditEventData,
    # Message types
    AuditLogMessage,
    BillingRequestMessage,
    ChatMessage,
    ClaimRequestMessage,
    EscalationRequestMessage,
    # Base types
    MessageData,
    PolicyRequestMessage,
    StreamChunkData,
    StreamChunkMessage,
    StreamEndData,
    StreamEndMessage,
    UserMessage,
    is_agent_message,
    # Type guards
    is_audit_log,
    is_billing_request,
    is_claim_request,
    is_escalation_request,
    is_policy_request,
    is_stream_end,
    is_user_message,
)

__all__ = [
    # Enums
    "MessageType",
    "AgentName",
    "AuditCategory",
    "OffsetReset",
    
    # Data types
    "MessageData",
    "ChatMessage",
    "AgentRequestData",
    "AgentResponseData",
    "StreamChunkData",
    "StreamEndData",
    "AuditEventData",
    
    # Message types
    "AuditLogMessage",
    "BillingRequestMessage",
    "ClaimRequestMessage",
    "PolicyRequestMessage",
    "EscalationRequestMessage",
    "UserMessage",
    "AgentMessage",
    "StreamChunkMessage",
    "StreamEndMessage",
    
    # Type guards
    "is_audit_log",
    "is_billing_request",
    "is_claim_request",
    "is_policy_request",
    "is_escalation_request",
    "is_user_message",
    "is_agent_message",
    "is_stream_end",
]