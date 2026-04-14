from __future__ import annotations

import os
from collections.abc import Callable
from contextlib import contextmanager
from typing import Any


class _NoOpSpan:
    def record_exception(self, exc):
        pass

    def set_error_status(self, description=""):
        pass

    def set_attribute(self, key, value):
        pass


class _OtelSpan:
    """Thin wrapper around a real OTel span that exposes set_error_status."""

    def __init__(self, span):
        self._span = span

    def record_exception(self, exc):
        self._span.record_exception(exc)

    def set_error_status(self, description=""):
        from opentelemetry.trace import StatusCode

        self._span.set_status(StatusCode.ERROR, description)

    def set_attribute(self, key, value):
        self._span.set_attribute(key, value)


class _NoOpBackend:
    is_noop = True

    @contextmanager
    def start_producer_span(self, channel_name, message):
        yield _NoOpSpan(), {}

    @contextmanager
    def start_consumer_span(self, channel_name, traceparent):
        yield _NoOpSpan()


class _OtelBackend:
    is_noop = False

    def __init__(self, tracer):
        self._tracer = tracer

    @contextmanager
    def start_producer_span(self, channel_name, message):
        from opentelemetry.propagate import extract as otel_extract
        from opentelemetry.propagate import inject as otel_inject
        from opentelemetry.trace import SpanKind

        existing_tp = (
            message.get("traceparent")
            if isinstance(message, dict)
            else getattr(message, "traceparent", None)
        )
        parent_ctx = otel_extract({"traceparent": existing_tp}) if existing_tp else None
        with self._tracer.start_as_current_span(
            f"eggai.publish {channel_name}",
            context=parent_ctx,
            kind=SpanKind.PRODUCER,
        ) as span:
            carrier: dict = {}
            otel_inject(carrier)
            yield _OtelSpan(span), carrier

    @contextmanager
    def start_consumer_span(self, channel_name, traceparent):
        from opentelemetry.propagate import extract as otel_extract
        from opentelemetry.trace import SpanKind

        parent_ctx = otel_extract({"traceparent": traceparent}) if traceparent else None
        with self._tracer.start_as_current_span(
            f"eggai.process {channel_name}",
            context=parent_ctx,
            kind=SpanKind.CONSUMER,
        ) as span:
            yield _OtelSpan(span)


try:
    from opentelemetry.trace import NoOpTracer as _probe  # noqa: F401

    _backend: _NoOpBackend | _OtelBackend | None = _NoOpBackend()
except ImportError:
    _backend = None


def get_backend():
    return _backend


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

    from opentelemetry.trace import ProxyTracerProvider

    if isinstance(trace.get_tracer_provider(), ProxyTracerProvider):
        trace.set_tracer_provider(provider)
    else:
        provider = trace.get_tracer_provider()

    from importlib.metadata import version

    global _backend
    _backend = _OtelBackend(trace.get_tracer("eggai", version("eggai")))


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
    Returns handler unchanged if OTel is not installed.
    """
    if _backend is None:
        return handler

    import asyncio
    import functools

    if not asyncio.iscoroutinefunction(handler):
        return handler

    @functools.wraps(handler)
    async def traced_handler(message):
        traceparent = (
            message.get("traceparent")
            if isinstance(message, dict)
            else getattr(message, "traceparent", None)
        )
        with _backend.start_consumer_span(channel_name, traceparent) as span:
            _set_span_attrs(span, channel_name, message, "process")
            try:
                return await handler(message)
            except Exception as exc:
                span.record_exception(exc)
                span.set_error_status(str(exc))
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
