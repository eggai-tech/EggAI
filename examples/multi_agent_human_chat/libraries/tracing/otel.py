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


def safe_set_attribute(span, key: str, value: Any) -> None:
    """
    Safely set a span attribute, handling None values and unsupported types.
    
    Args:
        span: The OpenTelemetry span to set the attribute on
        key: The attribute key
        value: The attribute value
    """
    if value is None:
        # Skip None values
        return
        
    # Handle basic types
    if isinstance(value, (bool, int, float, str, bytes)):
        span.set_attribute(key, value)
    # Handle lists of basic types
    elif isinstance(value, list) and all(isinstance(item, (bool, int, float, str, bytes)) for item in value):
        span.set_attribute(key, value)
    # Convert other types to string representation
    else:
        try:
            span.set_attribute(key, str(value))
        except Exception:
            # If all else fails, we just skip the attribute
            pass


def init_telemetry(
    app_name: str,
    endpoint: Optional[str] = None,
    **kwargs
) -> None:
    import openlit
    otlp_endpoint = endpoint or os.getenv("OTEL_ENDPOINT", "http://localhost:4318")
    config = {
        "application_name": app_name,
        "otlp_endpoint": otlp_endpoint,
        "disabled_instrumentors": ["langchain"],
    }
    config.update(kwargs)
    openlit.init(**config)


_TRACERS: Dict[str, Tracer] = {}

def get_tracer(name: str) -> Tracer:
    if name not in _TRACERS:
        _TRACERS[name] = trace.get_tracer(name)
    return _TRACERS[name]


def _normalize_name(name: str) -> str:
    return name.lower().replace(" ", "_").replace("-", "_")


def create_tracer(name: str, component: Optional[str] = None) -> Tracer:
    normalized = _normalize_name(name)
    tracer_name = f"{normalized}.{_normalize_name(component)}" if component else normalized
    return get_tracer(tracer_name)


def extract_span_context(traceparent: str, tracestate: str = None) -> Optional[SpanContext]:
    parts = traceparent.split('-')
    if len(parts) != 4 or parts[0] != '00':
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
        trace_state=state
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
            from libraries.logger import get_console_logger
            from libraries.tracing.schemas import TracedMessage

            splitted = handler_func.__module__.split('.')
            module_name = splitted[-2] if len(splitted) > 1 else splitted[0]
            tracer_name = f"{module_name}_agent"
            tracer = get_tracer(tracer_name)
            logger = get_console_logger(f"{tracer_name}.handler")

            msg = next((arg for arg in args if isinstance(arg, TracedMessage)), None)
            if not msg:
                msg = next((v for v in kwargs.values() if isinstance(v, TracedMessage)), None)
            if not msg:
                raw = next((arg for arg in args if isinstance(arg, dict)), None) or \
                      next((v for v in kwargs.values() if isinstance(v, dict)), None)
                if raw:
                    msg = TracedMessage(**raw)

            if isinstance(msg, dict) and isinstance(msg.get('channel'), dict):
                original = msg['channel']
                msg['channel'] = original.get('channel') or json.dumps(original)

            parent_context = None
            traceparent = getattr(msg, 'traceparent', None)
            tracestate = getattr(msg, 'tracestate', None)
            if traceparent:
                span_ctx = extract_span_context(traceparent, tracestate)
                if span_ctx:
                    parent_context = trace.set_span_in_context(trace.NonRecordingSpan(span_ctx))

            span_name_to_use = span_name or f"handle_{module_name}_message"
            with tracer.start_as_current_span(
                span_name_to_use,
                context=parent_context,
                kind=trace.SpanKind.SERVER
            ) as span:
                safe_set_attribute(span, "agent.name", module_name)
                safe_set_attribute(span, "agent.handler", handler_func.__name__)
                safe_set_attribute(span, "message.id", str(getattr(msg, 'id', 'unknown')))

                if iscoroutine(handler_func) or asyncio.iscoroutinefunction(handler_func):
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
