"""
OpenTelemetry initialization and configuration utilities.

This module provides centralized configuration and tracer creation for OpenTelemetry.
"""

import functools
import os
from typing import Optional, Dict, Any, Callable, TypeVar, cast

from opentelemetry import trace
from opentelemetry.trace import Tracer

# Type variables for function decorators
F = TypeVar('F', bound=Callable[..., Any])
AF = TypeVar('AF', bound=Callable[..., Any])


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


def trace_function(
    func: Optional[F] = None,
    *, 
    name: Optional[str] = None, 
    tracer: Optional[trace.Tracer] = None
) -> Callable[[F], F]:
    """
    Decorator to trace a function with OpenTelemetry.
    
    Can be used as @trace_function or @trace_function(name="custom_name")
    
    Args:
        func: Function to trace when used as @trace_function
        name: Optional name for the span (defaults to function name)
        tracer: Optional specific tracer to use (defaults to function module)
        
    Returns:
        Traced function
    """
    def decorator(fn: F) -> F:
        span_name = name or fn.__name__
        func_tracer = tracer or trace.get_tracer(fn.__module__)
        
        @functools.wraps(fn)
        def wrapped(*args: Any, **kwargs: Any) -> Any:
            with func_tracer.start_as_current_span(span_name):
                return fn(*args, **kwargs)
                
        return cast(F, wrapped)
    
    # Handle both @trace_function and @trace_function() usage
    if func is None:
        return decorator
    return decorator(func)


def async_trace_function(
    func: Optional[AF] = None,
    *,
    name: Optional[str] = None,
    tracer: Optional[trace.Tracer] = None
) -> Callable[[AF], AF]:
    """
    Decorator to trace an async function with OpenTelemetry.
    
    Can be used as @async_trace_function or @async_trace_function(name="custom_name")
    
    Args:
        func: Async function to trace when used as @async_trace_function
        name: Optional name for the span (defaults to function name)
        tracer: Optional specific tracer to use (defaults to function module)
        
    Returns:
        Traced async function
    """
    def decorator(fn: AF) -> AF:
        span_name = name or fn.__name__
        func_tracer = tracer or trace.get_tracer(fn.__module__)
        
        @functools.wraps(fn)
        async def wrapped(*args: Any, **kwargs: Any) -> Any:
            with func_tracer.start_as_current_span(span_name):
                return await fn(*args, **kwargs)
                
        return cast(AF, wrapped)
    
    # Handle both @async_trace_function and @async_trace_function() usage
    if func is None:
        return decorator
    return decorator(func)