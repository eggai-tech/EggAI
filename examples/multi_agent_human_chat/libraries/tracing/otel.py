"""
OpenTelemetry initialization and configuration utilities.

This module provides centralized configuration and tracer creation for OpenTelemetry.
"""

import asyncio
import functools
import json
import os
import random
import uuid
from asyncio import iscoroutine
from typing import Any, Awaitable, Callable, Dict, Optional

from opentelemetry import trace
from opentelemetry.trace import SpanContext, TraceFlags, Tracer, TraceState

from libraries.logger import get_console_logger

logger = get_console_logger("tracing.dspy")


def safe_set_attribute(span, key: str, value: Any) -> None:
    """
    Safely set a span attribute, handling None values and unsupported types.

    Args:
        span: The OpenTelemetry span to set the attribute on
        key: The attribute key
        value: The attribute value
    """
    if value is None:
        # Skip None values entirely
        return

    # For gen_ai attributes specifically, ensure we have string values
    if key.startswith("gen_ai."):
        if isinstance(value, (bool, int, float)):
            value = str(value)
        elif not isinstance(value, (str, bytes)) and not isinstance(value, list):
            try:
                value = str(value)
            except Exception:
                # If conversion fails, just skip it
                logger.debug(
                    f"Skipping gen_ai attribute {key} with unconvertible type: {type(value)}"
                )
                return

    # Handle basic types
    if isinstance(value, (bool, int, float, str, bytes)):
        try:
            span.set_attribute(key, value)
        except Exception as e:
            # If setting fails, try string conversion
            logger.debug(f"Error setting span attribute {key}: {e}")
            try:
                span.set_attribute(key, str(value))
            except Exception:
                logger.debug(
                    f"Failed to set attribute {key} even after string conversion"
                )
                pass

    # Handle lists of basic types
    elif isinstance(value, list) and all(
        isinstance(item, (bool, int, float, str, bytes)) for item in value
    ):
        try:
            span.set_attribute(key, value)
        except Exception:
            # List might be invalid - try converting the whole list to a string
            try:
                span.set_attribute(key, str(value))
            except Exception:
                logger.debug(f"Failed to set list attribute {key}")
                pass

    # Convert other types to string representation
    else:
        try:
            span.set_attribute(key, str(value))
        except Exception:
            # If all else fails, we just skip the attribute
            logger.debug(
                f"Skipping attribute {key} with invalid value type: {type(value)}"
            )
            pass


def init_telemetry(app_name: str, endpoint: Optional[str] = None, **kwargs) -> None:
    """
    Initialize OpenTelemetry.

    Args:
        app_name: The name of the application for OpenTelemetry
        endpoint: Optional OTLP endpoint URL (defaults to env OTEL_ENDPOINT or localhost)
        **kwargs: Additional configuration parameters (unused after openlit removal)
    """
    # Initialize OpenTelemetry directly
    from opentelemetry import trace
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    otlp_endpoint = endpoint or os.getenv("OTEL_ENDPOINT", "http://localhost:4318")

    # Set up resource
    resource = Resource.create({"service.name": app_name})

    # Set up tracer provider
    trace.set_tracer_provider(TracerProvider(resource=resource))

    # Set up OTLP exporter
    otlp_exporter = OTLPSpanExporter(endpoint=f"{otlp_endpoint}/v1/traces")

    # Add span processor
    span_processor = BatchSpanProcessor(otlp_exporter)
    trace.get_tracer_provider().add_span_processor(span_processor)

    # After initialization, get the actual Span class to patch
    # We need to do this after OpenTelemetry is initialized
    try:
        # Try to find the span implementation being used
        logger.info(
            "Attempting to patch span attribute setter for safer attribute handling"
        )
        from opentelemetry.sdk.trace import Span as SDKSpan
        from opentelemetry.trace import Span

        # Get actual implementation class - this will depend on the OpenTelemetry setup
        span_classes = []
        if hasattr(Span, "set_attribute"):
            span_classes.append(Span)
        if hasattr(SDKSpan, "set_attribute"):
            span_classes.append(SDKSpan)

        # Patch any classes we found
        for span_class in span_classes:
            if hasattr(span_class, "set_attribute"):
                logger.info(
                    f"Patching {span_class.__name__}.set_attribute for safe attribute handling"
                )
                original_set_attribute = span_class.set_attribute

                # Create a closure to properly capture original_set_attribute
                def create_safe_middleware(original_method):
                    def safe_set_attribute_middleware(self, key: str, value: Any):
                        # Skip None values entirely
                        if value is None:
                            return self

                        # For gen_ai attributes specifically, ensure we have string values
                        if key.startswith("gen_ai."):
                            if isinstance(value, (bool, int, float)):
                                value = str(value)
                            elif not isinstance(value, (str, bytes)):
                                try:
                                    value = str(value)
                                except Exception:
                                    # If conversion fails, just skip it
                                    return self

                        # For other attribute types, follow normal OTel rules but with added safety
                        try:
                            return original_method(self, key, value)
                        except Exception:
                            # Try to convert to string as a last resort
                            try:
                                return original_method(self, key, str(value))
                            except Exception:
                                # If all else fails, just skip this attribute
                                return self

                    return safe_set_attribute_middleware

                # Apply the patch with proper binding
                span_class.set_attribute = create_safe_middleware(
                    original_set_attribute
                )
                logger.info(f"Successfully patched {span_class.__name__}.set_attribute")
    except Exception as e:
        # If patching fails, log but continue - we'll rely on safe_set_attribute instead
        logger.warning(
            f"Unable to patch span attribute setter: {e}. Using manual safe_set_attribute instead."
        )


_TRACERS: Dict[str, Tracer] = {}


def get_tracer(name: str) -> Tracer:
    if name not in _TRACERS:
        _TRACERS[name] = trace.get_tracer(name)
    return _TRACERS[name]


def _normalize_name(name: str) -> str:
    return name.lower().replace(" ", "_").replace("-", "_")


def create_tracer(name: str, component: Optional[str] = None) -> Tracer:
    normalized = _normalize_name(name)
    tracer_name = (
        f"{normalized}.{_normalize_name(component)}" if component else normalized
    )
    return get_tracer(tracer_name)


def extract_span_context(
    traceparent: str, tracestate: str = None
) -> Optional[SpanContext]:
    parts = traceparent.split("-")
    if len(parts) != 4 or parts[0] != "00":
        return None
    try:
        trace_id = int(parts[1], 16)
        span_id = int(parts[2], 16)
        trace_flags = TraceFlags(int(parts[3], 16))
    except Exception:
        return None
    state = TraceState.from_header(tracestate) if tracestate else TraceState()
    return SpanContext(
        trace_id=trace_id,
        span_id=span_id,
        is_remote=True,
        trace_flags=trace_flags,
        trace_state=state,
    )


def format_span_as_traceparent(span) -> tuple:
    sc = span.get_span_context()
    traceparent = f"00-{sc.trace_id:032x}-{sc.span_id:016x}-{int(sc.trace_flags):02x}"
    tracestate = str(sc.trace_state) if sc.trace_state else ""
    return traceparent, tracestate


def traced_handler(span_name: str = None):
    def decorator(handler_func: Callable[[Dict], Awaitable[None]]):
        @functools.wraps(handler_func)
        async def wrapper(*args, **kwargs):
            from libraries.tracing.schemas import TracedMessage

            splitted = handler_func.__module__.split(".")
            module_name = splitted[-2] if len(splitted) > 1 else splitted[0]
            tracer_name = f"{module_name}_agent"
            tracer = get_tracer(tracer_name)

            msg = next((arg for arg in args if isinstance(arg, TracedMessage)), None)
            if not msg:
                msg = next(
                    (v for v in kwargs.values() if isinstance(v, TracedMessage)), None
                )
            if not msg:
                raw = next(
                    (arg for arg in args if isinstance(arg, dict)), None
                ) or next((v for v in kwargs.values() if isinstance(v, dict)), None)
                if raw:
                    msg = TracedMessage(**raw)

            if isinstance(msg, dict) and isinstance(msg.get("channel"), dict):
                original = msg["channel"]
                msg["channel"] = original.get("channel") or json.dumps(original)

            parent_context = None
            traceparent = getattr(msg, "traceparent", None)
            tracestate = getattr(msg, "tracestate", None)
            if traceparent:
                span_ctx = extract_span_context(traceparent, tracestate)
                if span_ctx:
                    parent_context = trace.set_span_in_context(
                        trace.NonRecordingSpan(span_ctx)
                    )

            span_name_to_use = span_name or f"handle_{module_name}_message"
            with tracer.start_as_current_span(
                span_name_to_use, context=parent_context, kind=trace.SpanKind.SERVER
            ) as span:
                safe_set_attribute(span, "agent.name", module_name)
                safe_set_attribute(span, "agent.handler", handler_func.__name__)
                safe_set_attribute(
                    span, "message.id", str(getattr(msg, "id", "unknown"))
                )

                if iscoroutine(handler_func) or asyncio.iscoroutinefunction(
                    handler_func
                ):
                    return await handler_func(*args, **kwargs)
                else:
                    return handler_func(*args, **kwargs)

        return wrapper

    return decorator


def get_traceparent_from_connection_id(connection_id: str) -> str:
    connection_uuid = uuid.UUID(connection_id)
    trace_id = connection_uuid.hex
    span_id = f"{random.getrandbits(64):016x}"
    trace_flags = "01"
    return f"00-{trace_id}-{span_id}-{trace_flags}"
