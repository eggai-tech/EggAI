"""
Tracing utilities for instrumentation.

This package provides utilities for tracing functions, methods, and DSPy modules,
as well as OpenTelemetry initialization and configuration.
"""

from libraries.tracing.otel import (
    init_telemetry, 
    get_tracer, 
    create_tracer,
)

from libraries.tracing.dspy import (
    TracedChainOfThought,
    TracedReAct,
)

__all__ = [
    # OpenTelemetry utilities
    "init_telemetry",
    "get_tracer",
    "create_tracer",
    # DSPy-module-specific tracing
    "TracedChainOfThought",
    "TracedReAct",
]