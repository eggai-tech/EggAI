"""
OpenTelemetry initialization and configuration utilities.

This module provides centralized configuration and tracer creation for OpenTelemetry.
"""

import functools
import os
import random
import uuid
from typing import Optional, Dict, Callable, Awaitable

from opentelemetry import trace
from opentelemetry.trace import Tracer, SpanContext, TraceFlags, TraceState


def init_telemetry(
    app_name: str,
    endpoint: Optional[str] = None,
    **kwargs
) -> None:
    """
    Initialize OpenTelemetry for the application.
    
    This is a wrapper around openlit.init that centralizes the initialization.
    
    Args:
        app_name: Name of the application/agent for telemetry
        endpoint: OTLP endpoint URL (defaults to OTEL_ENDPOINT env var or http://localhost:4318)
        **kwargs: Additional parameters to pass to openlit.init
    """
    import openlit
    
    # Get endpoint from env var if not provided
    otlp_endpoint = endpoint or os.getenv("OTEL_ENDPOINT", "http://localhost:4318")
    
    # Default configuration that can be overridden by kwargs
    config = {
        "application_name": app_name,
        "otlp_endpoint": otlp_endpoint,
        # By default, disable langchain instrumentation as it's not used in our agents
        "disabled_instrumentors": ["langchain"],
    }
    
    # Override defaults with any provided kwargs
    config.update(kwargs)
    
    # Initialize OpenTelemetry
    openlit.init(**config)


# Cache for tracers to avoid creating duplicates
_TRACERS: Dict[str, Tracer] = {}


def get_tracer(name: str) -> Tracer:
    """
    Get a tracer by name with caching.
    
    Args:
        name: The name for the tracer, typically the module name
        
    Returns:
        A tracer instance that can be used to create spans
    """
    if name not in _TRACERS:
        _TRACERS[name] = trace.get_tracer(name)
    return _TRACERS[name]


def _normalize_name(name: str) -> str:
    """
    Normalize a name for use in tracer names.
    
    Args:
        name: The name to normalize
        
    Returns:
        Normalized name (lowercase with spaces and hyphens replaced with underscores)
    """
    return name.lower().replace(" ", "_").replace("-", "_")


def create_tracer(name: str, component: Optional[str] = None) -> Tracer:
    """
    Create a standardized tracer with consistent naming.
    
    Args:
        name: The base name for the tracer (e.g., "billing", "triage")
        component: Optional component name (e.g., "rag", "dspy", "api")
        
    Returns:
        A tracer instance with a standardized name
    """
    normalized_name = _normalize_name(name)
    
    if component:
        normalized_component = _normalize_name(component)
        tracer_name = f"{normalized_name}.{normalized_component}"
    else:
        tracer_name = normalized_name
        
    return get_tracer(tracer_name)


def extract_span_context(traceparent: str, tracestate: str = None) -> SpanContext:
    """
    Extract SpanContext from traceparent and tracestate strings.
    
    Args:
        traceparent: W3C traceparent header (format: "00-{trace_id}-{span_id}-{trace_flags}")
        tracestate: Optional W3C tracestate header
        
    Returns:
        SpanContext object or None if traceparent format is invalid
    """
    # Parse traceparent format: "00-{trace_id}-{span_id}-{trace_flags}"
    parts = traceparent.split('-')
    if len(parts) != 4 or parts[0] != '00':
        return None
    
    trace_id = int(parts[1], 16)
    span_id = int(parts[2], 16)
    trace_flags = TraceFlags(int(parts[3], 16))
    
    trace_state_obj = TraceState.from_header(tracestate) if tracestate else TraceState()
    return SpanContext(
        trace_id=trace_id,
        span_id=span_id,
        is_remote=True,
        trace_flags=trace_flags,
        trace_state=trace_state_obj
    )


def format_span_as_traceparent(span) -> tuple:
    """
    Format current span into traceparent and tracestate strings.
    
    Args:
        span: The current span object
        
    Returns:
        Tuple of (traceparent, tracestate) strings
    """
    span_context = span.get_span_context()
    
    # Format traceparent: "00-{trace_id}-{span_id}-{trace_flags}"
    traceparent = f"00-{span_context.trace_id:032x}-{span_context.span_id:016x}-{int(span_context.trace_flags):02x}"
    
    # Format tracestate 
    tracestate = str(span_context.trace_state) if span_context.trace_state else ""
    
    return traceparent, tracestate


def traced_handler(span_name: str = None):
    """
    A decorator for agent message handlers that ensures proper tracing.
    
    This decorator:
    1. Extracts trace context from incoming messages
    2. Creates a new span with the extracted context as parent or starts a new trace
    3. Ensures the span is properly closed when the handler completes
    
    Args:
        span_name: Optional name for the span (defaults to the decorated function's name)
        
    Returns:
        A decorator function that wraps the handler with tracing logic
    """
    def decorator(handler_func: Callable[[Dict], Awaitable[None]]):
        @functools.wraps(handler_func)
        async def wrapper(*args, **kwargs):
            # Import here to avoid circular dependencies
            from libraries.tracing.schemas import TracedMessage
            from libraries.logger import get_console_logger
            
            # Get the agent name from the function's module
            module_name = handler_func.__module__.split('.')[-2]  # e.g., "triage" from "agents.triage.agent"
            tracer_name = f"{module_name}_agent"
            
            # Create a tracer for this handler
            tracer = get_tracer(tracer_name)
            logger = get_console_logger(f"{tracer_name}.handler")
            
            try:
                msg = next((arg for arg in args if isinstance(arg, TracedMessage)), None)
                if not msg:
                    msg = next((arg for arg in kwargs.values() if isinstance(arg, TracedMessage)), None)

                # If no message is found, try to find a dict
                if not msg:
                    msg = next((arg for arg in args if isinstance(arg, dict)), None)
                    if not msg:
                        msg = next((arg for arg in kwargs.values() if isinstance(arg, dict)), None)

                    if msg:
                        msg = TracedMessage(**msg)

                
                # Extract parent context from the incoming message if available
                parent_context = None
                if getattr(msg, 'traceparent', None):
                    try:
                        span_context = extract_span_context(msg.traceparent, getattr(msg, 'tracestate', None))
                        if span_context:
                            # Create a parent context with a NonRecordingSpan - this links to parent 
                            # without modifying the parent span
                            parent_context = trace.set_span_in_context(trace.NonRecordingSpan(span_context))
                    except Exception as e:
                        logger.warning(f"Failed to extract span context: {e}")
                
                # Use the provided span_name or default to the handler function name
                span_name_to_use = span_name or f"handle_{module_name}_message"
                
                # Create a new span for handling this message
                # Use the root span (no context) if we couldn't extract a valid parent
                context = parent_context
                
                span_kind = trace.SpanKind.SERVER  # Mark as a server span to show this as handling a request
                with tracer.start_as_current_span(
                    span_name_to_use, 
                    context=context,
                    kind=span_kind
                ) as span:
                    # Set standard attributes
                    span.set_attribute("agent.name", module_name)
                    span.set_attribute("agent.handler", handler_func.__name__)
                    span.set_attribute("message.id", str(getattr(msg, 'id', 'unknown')))
                    
                    # Call the original handler function
                    result = await handler_func(*args, **kwargs)
                    return result
            except Exception as e:
                logger.error(f"Error in traced handler: {e}", exc_info=True)
                # Ensure we re-raise so the error is properly handled
                raise
                
        return wrapper
    return decorator

def get_traceparent_from_connection_id(connection_id: str) -> str:
    connection_uuid = uuid.UUID(connection_id)
    trace_id = connection_uuid.hex
    span_id = f"{random.getrandbits(64):016x}"
    trace_flags = "01"
    return f"00-{trace_id}-{span_id}-{trace_flags}"