"""
Tracing utilities for instrumentation.

This package provides utilities for tracing functions, methods, and DSPy modules,
as well as OpenTelemetry initialization and configuration.
"""

from libraries.tracing.dspy import (
    TracedChainOfThought,
    TracedReAct,
    add_gen_ai_attributes_to_span,
    traced_dspy_function,
)
from libraries.tracing.otel import (
    create_tracer,
    extract_span_context,
    format_span_as_traceparent,
    get_tracer,
    init_telemetry,
    safe_set_attribute,
    traced_handler,
)
from libraries.tracing.schemas import GenAIAttributes, TracedMessage

__all__ = [
    # OpenTelemetry utilities
    "TracedMessage",
    "GenAIAttributes",
    "init_telemetry",
    "get_tracer",
    "create_tracer",
    "extract_span_context",
    "format_span_as_traceparent",
    "traced_handler",
    "safe_set_attribute",
    # DSPy-module-specific tracing
    "TracedChainOfThought",
    "TracedReAct",
    "traced_dspy_function",
    "add_gen_ai_attributes_to_span",
]