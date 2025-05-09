"""
Tracing utilities for instrumentation.

This package provides utilities for tracing functions, methods, and DSPy modules,
as well as OpenTelemetry initialization and configuration.
"""

from libraries.tracing.schemas import (
    TracedMessage
)

from libraries.tracing.otel import (
    init_telemetry, 
    get_tracer, 
    create_tracer,
    extract_span_context,
    format_span_as_traceparent,
    traced_handler,
)

from libraries.tracing.dspy import (
    TracedChainOfThought,
    TracedReAct,
    traced_dspy_function,
)

__all__ = [
    # OpenTelemetry utilities
    "TracedMessage",
    "init_telemetry",
    "get_tracer",
    "create_tracer",
    "extract_span_context",
    "format_span_as_traceparent",
    "traced_handler",
    # DSPy-module-specific tracing
    "TracedChainOfThought",
    "TracedReAct",
    "traced_dspy_function",
]