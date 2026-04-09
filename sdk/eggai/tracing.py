from __future__ import annotations

import os
from collections.abc import Callable
from typing import Any

_tracer = None  # None until setup_tracing() is called


def setup_tracing(
    exporter="otlp",
    *,
    service_name: str | None = None,
    endpoint: str | None = None,
):
    """Activate EggAI tracing. Call once at app startup."""
    from opentelemetry import trace
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

    resource = Resource.create(
        {"service.name": service_name or os.getenv("OTEL_SERVICE_NAME", "eggai")}
    )
    provider = TracerProvider(resource=resource)

    if exporter == "console":
        span_exporter = ConsoleSpanExporter()
    elif exporter == "otlp-http":
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
            OTLPSpanExporter,
        )

        span_exporter = OTLPSpanExporter(**({"endpoint": endpoint} if endpoint else {}))
    elif hasattr(exporter, "export"):
        span_exporter = exporter  # accept pre-built exporter object (for testing)
    else:  # "otlp" / "otlp-grpc" (default)
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
            OTLPSpanExporter,
        )

        span_exporter = OTLPSpanExporter(**({"endpoint": endpoint} if endpoint else {}))

    provider.add_span_processor(BatchSpanProcessor(span_exporter))
    trace.set_tracer_provider(provider)

    import eggai

    global _tracer
    _tracer = trace.get_tracer("eggai", eggai.__version__)


def get_tracer():
    return _tracer


def apply_traceparent(message: Any, traceparent: str) -> Any:
    """Return message with traceparent set (creates new Pydantic model instance or dict copy)."""
    from pydantic import BaseModel

    if isinstance(message, BaseModel):
        return message.model_copy(update={"traceparent": traceparent})
    if isinstance(message, dict):
        return {**message, "traceparent": traceparent}
    return message


def make_tracing_wrapper(channel_name: str, handler: Callable) -> Callable:
    """
    Wrap a message handler to extract trace context and create a child consumer span.
    Returns handler unchanged if tracing is not active.
    """
    if _tracer is None:
        return handler

    from opentelemetry.propagate import extract as otel_extract
    from opentelemetry.trace import SpanKind, StatusCode

    async def traced_handler(message):
        traceparent = None
        if isinstance(message, dict):
            traceparent = message.get("traceparent")
        elif hasattr(message, "traceparent"):
            traceparent = message.traceparent

        parent_ctx = otel_extract({"traceparent": traceparent}) if traceparent else None

        with _tracer.start_as_current_span(
            f"eggai.process {channel_name}",
            context=parent_ctx,
            kind=SpanKind.CONSUMER,
        ) as span:
            _set_span_attrs(span, channel_name, message, "process")
            try:
                return await handler(message)
            except Exception as exc:
                span.record_exception(exc)
                span.set_status(StatusCode.ERROR, str(exc))
                raise

    return traced_handler


def _set_span_attrs(span, channel_name: str, message: Any, operation: str):
    span.set_attribute("messaging.system", "eggai")
    span.set_attribute("messaging.destination", channel_name)
    span.set_attribute("messaging.operation", operation)
    if hasattr(message, "id"):
        span.set_attribute("eggai.message.id", str(message.id))
    if hasattr(message, "type"):
        span.set_attribute("eggai.message.type", message.type)
    if hasattr(message, "source"):
        span.set_attribute("eggai.message.source", message.source)


# Auto-activate if OTEL env vars present (silently skip if otel extra not installed)
if os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT"):
    try:
        _protocol = os.getenv("OTEL_EXPORTER_OTLP_PROTOCOL", "grpc")
        _exporter = "otlp-http" if "http" in _protocol else "otlp"
        setup_tracing(exporter=_exporter)
    except ImportError:
        pass
