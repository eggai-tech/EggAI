import asyncio
import functools
from typing import Any, Callable, Dict, Optional

from opentelemetry import trace
from opentelemetry.trace import Span

# Get the current tracer
tracer = trace.get_tracer(__name__)


def safe_set_attribute(span: Span, key: str, value: Any) -> None:
    """
    Safely set an attribute on a span, handling None values and other edge cases.
    
    Args:
        span: The span to set the attribute on
        key: The attribute key
        value: The attribute value
    """
    if value is None:
        # Convert None to "None" string to avoid issues
        span.set_attribute(key, "None")
        return
    
    try:
        # Handle different types of values
        if isinstance(value, (str, bool, int, float)):
            span.set_attribute(key, value)
        elif isinstance(value, (list, tuple)):
            # For lists, set a count attribute and individual items if small enough
            span.set_attribute(f"{key}.count", len(value))
            if len(value) <= 10:  # Only set individual items for small lists
                for i, item in enumerate(value):
                    safe_set_attribute(span, f"{key}.{i}", str(item))
        elif isinstance(value, dict):
            # For dicts, set a count attribute and flatten keys if small enough
            span.set_attribute(f"{key}.count", len(value))
            if len(value) <= 10:  # Only set individual items for small dicts
                for k, v in value.items():
                    safe_set_attribute(span, f"{key}.{k}", str(v))
        else:
            # For any other type, convert to string
            span.set_attribute(key, str(value))
    except Exception:
        # If anything goes wrong, set a fallback value
        span.set_attribute(key, f"<non-serializable: {type(value).__name__}>")


def traced(span_name: Optional[str] = None):
    """
    Decorator to add OpenTelemetry tracing to functions or methods.
    
    Args:
        span_name: Optional name for the span. If not provided, the function name will be used.
    
    Returns:
        The decorated function with tracing.
    """

    def decorator(func: Callable):
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            nonlocal span_name
            if span_name is None:
                span_name = func.__name__
                
            with tracer.start_as_current_span(span_name) as span:
                # Add function name as attribute
                span.set_attribute("function", func.__name__)
                
                # Add args count as attribute
                span.set_attribute("args_count", len(args))
                span.set_attribute("kwargs_count", len(kwargs))
                
                # Capture start time
                try:
                    # Execute the function
                    result = await func(*args, **kwargs)
                    
                    # Add success attribute
                    span.set_attribute("status", "success")
                    
                    return result
                except Exception as e:
                    # Record exception and set error status
                    span.record_exception(e)
                    span.set_attribute("status", "error")
                    span.set_attribute("error.type", e.__class__.__name__)
                    span.set_attribute("error.message", str(e))
                    raise
                
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            nonlocal span_name
            if span_name is None:
                span_name = func.__name__
                
            with tracer.start_as_current_span(span_name) as span:
                # Add function name as attribute
                span.set_attribute("function", func.__name__)
                
                # Add args count as attribute
                span.set_attribute("args_count", len(args))
                span.set_attribute("kwargs_count", len(kwargs))
                
                try:
                    # Execute the function
                    result = func(*args, **kwargs)
                    
                    # Add success attribute
                    span.set_attribute("status", "success")
                    
                    return result
                except Exception as e:
                    # Record exception and set error status
                    span.record_exception(e)
                    span.set_attribute("status", "error")
                    span.set_attribute("error.type", e.__class__.__name__)
                    span.set_attribute("error.message", str(e))
                    raise
        
        # Check if the function is async
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


def get_current_span_context():
    """Get the current span context for linking spans across processes."""
    return trace.get_current_span().get_span_context()


def with_span_attributes(attributes: Dict[str, Any]):
    """
    Decorator to add attributes to the current span.
    
    Args:
        attributes: Dictionary of attributes to add to the span
        
    Returns:
        Decorator function
    """
    def decorator(func: Callable):
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            span = trace.get_current_span()
            for key, value in attributes.items():
                safe_set_attribute(span, key, value)
                
            return await func(*args, **kwargs)
                
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            span = trace.get_current_span()
            for key, value in attributes.items():
                safe_set_attribute(span, key, value)
                
            return func(*args, **kwargs)
        
        # Check if the function is async
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
            
    return decorator 