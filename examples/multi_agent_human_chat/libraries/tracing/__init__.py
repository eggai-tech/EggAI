"""
Tracing utilities for instrumentation.

This package provides utilities for tracing functions, methods, and DSPy modules,
as well as OpenTelemetry initialization and configuration.
"""

from libraries.tracing.otel import (
    init_telemetry, 
    get_tracer, 
    create_tracer,
    trace_function,
    async_trace_function,
)

from libraries.tracing.dspy import (
    TracedChainOfThought,
    TracedReAct,
)

__all__ = [
    # OpenTelemetry utilities
    "trace_function",
    "async_trace_function",
    "init_telemetry",
    "get_tracer",
    "create_tracer",
    # DSPy-module-specific tracing
    "TracedChainOfThought",
    "TracedReAct",
]