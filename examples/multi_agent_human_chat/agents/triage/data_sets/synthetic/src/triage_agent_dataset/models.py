from enum import Enum
from typing import Optional

from pydantic import BaseModel


class Agents(str, Enum):
    BILLING = "BillingAgent"
    POLICY = "PolicyAgent"
    CLAIMS = "ClaimsAgent"
    ESCALATION = "EscalationAgent"
    CHATTY = "ChattyAgent"

class SpecialCaseType(str, Enum):
    EDGE_CASE = "edge_case"
    CROSS_DOMAIN = "cross_domain"
    LANGUAGE_SWITCH = "language_switch"
    SHORT_QUERY = "short_query"
    COMPLEX_QUERY = "complex_query"
    SMALL_TALK = "small_talk"
    ANGRY_CUSTOMER = "angry_customer"
    TECHNICAL_ERROR = "technical_error"

class ConversationExample(BaseModel):
    conversation: str
    target_agent: str
    turns: int
    temperature: float
    index_batch: int
    total_batch: int
    special_case: Optional[str] = None
    model: str
