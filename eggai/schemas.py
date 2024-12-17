from pydantic import BaseModel, Field, UUID4
from typing import Optional, Dict, Any


class MessageBase(BaseModel):
    """
    Base class for all messages in the communication protocol.
    Provides the common fields required for every message.
    """
    id: UUID4 = Field(..., description="Unique identifier for correlating requests and responses.")
    message_type: str = Field(..., description="Type of the message (e.g., request, response, event).")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional metadata for the message.")
    payload: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Message-specific data.")
