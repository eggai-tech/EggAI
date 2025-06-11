import uuid
from typing import Dict, Optional, Generic, TypeVar

from eggai.schemas import Message
from pydantic import BaseModel, Field


# TODO make traceparent required and remove default
class TracedMessage(Message):
    """
    Message with OpenTelemetry tracing information embedded.

    Implements the W3C TraceContext for CloudEvents:
    - traceparent: Contains version, trace ID, span ID, and trace options
    - tracestate: Optional comma-delimited list of key-value pairs

    This extension enables distributed tracing across multiple services that
    process CloudEvents by carrying the OpenTelemetry context information.
    """

    traceparent: Optional[str] = Field(
        default=None,
        description="W3C trace context traceparent header (version-traceID-spanID-flags)",
    )
    tracestate: Optional[str] = Field(
        default=None,
        description="W3C trace context tracestate header with vendor-specific trace info",
    )
    service_tier: Optional[str] = Field(
        default="standard",
        description="Service tier for gen_ai spans (standard, premium, etc.)",
    )

TData = TypeVar("TData", bound=Dict[str, str], covariant=True)

class TracedTypedMessage(TracedMessage, Generic[TData]):
    data: TData = Field(
        default_factory=dict,
        description="Application-specific event payload with OpenTelemetry tracing information",
    )


class GenAIAttributes(BaseModel):
    """
    Model for gen_ai spans in OpenTelemetry to ensure proper attribute handling.
    This prevents errors when attributes are missing or have invalid types.

    All fields that are required by OpenTelemetry specifications have default values
    to avoid None or missing value errors.
    """

    model_provider: str = Field(default="unknown")
    model_name: str = Field(default="unknown")
    request_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    response_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service_tier: str = Field(default="standard")
    token_count: Optional[int] = None

    def to_span_attributes(self) -> Dict[str, str]:
        """
        Convert to dictionary of span attributes with gen_ai prefix.

        Returns:
            Dict with gen_ai prefixed attributes, skipping None values
        """
        result = {}
        for key, value in self.model_dump().items():
            if value is not None:
                # Ensure all values are strings if they're not already
                if not isinstance(value, str) and not isinstance(value, (list, bytes)):
                    value = str(value)
                result[f"gen_ai.{key}"] = value
        return result
