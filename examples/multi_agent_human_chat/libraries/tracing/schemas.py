from typing import Optional
from pydantic import Field
from eggai.schemas import Message

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
        description="W3C trace context traceparent header (version-traceID-spanID-flags)"
    )
    tracestate: Optional[str] = Field(
        default=None,
        description="W3C trace context tracestate header with vendor-specific trace info"
    )