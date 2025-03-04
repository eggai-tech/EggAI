import uuid
from datetime import datetime
from typing import Generic, Optional, TypeVar, Dict, Any

from pydantic import BaseModel, Field, UUID4

# Define type variables with defaults (requires Python 3.11+ for default values on TypeVar)
TData = TypeVar("TData")

class BaseMessage(BaseModel, Generic[TData]):
    """
    Generic Message Model for Agent Messaging Protocol.

    This model follows the CloudEvents 1.0 specification and integrates
    metadata and context as CloudEvents-compliant extension attributes.

    The model is generic so that you can specify custom Pydantic models 
    for data, the application-specific event payload.
    By default, if no custom model is provided, data is a dictionary.

    Fields:
        specversion (str): CloudEvents version (always "1.0").
        id (UUID4): Unique event identifier.
        source (str): Identifies the event producer.
        type (str): Event type (e.g., "user.created", "order.shipped").
        subject (Optional[str]): Subject of the event.
        time (Optional[datetime]): Timestamp of event creation.
        datacontenttype (Optional[str]): Media type of the event data.
        dataschema (Optional[str]): URI of the schema that `data` adheres to.
        data (TData): Application-specific event payload.
    """
    specversion: str = Field(default="1.0", description="CloudEvents specification version (always '1.0').")
    id: UUID4 = Field(default_factory=uuid.uuid4, description="Unique identifier for correlating events and ensuring idempotency.")
    source: str = Field(..., description="Identifies the event producer (e.g., '/service-a').")
    type: str = Field(..., description="Event type (e.g., 'user.created', 'order.shipped').")
    subject: Optional[str] = Field(default=None, description="Subject of the event in the context of the producer.")
    time: Optional[datetime] = Field(default_factory=datetime.utcnow, description="Timestamp of when the event was created (ISO 8601).")
    datacontenttype: Optional[str] = Field(default="application/json", description="Media type of the event data.")
    dataschema: Optional[str] = Field(default=None, description="URI of the schema that `data` adheres to.")
    data: TData = Field(default_factory=dict, description="Event payload containing application-specific data.")

# Create a concrete version with dict defaults.
class Message(BaseMessage[Dict[str, Any]]):
    """
    Concrete Message model with `data` defaulting to dict.
    """
    pass