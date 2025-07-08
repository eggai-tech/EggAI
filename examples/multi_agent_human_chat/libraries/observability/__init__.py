"""
Observability utilities for monitoring and debugging EggAI agents.

This module provides logging, tracing, and metrics functionality.
"""

# Re-export commonly used functions for convenience
from .logger import configure_logging, get_console_logger
from .tracing import TracedMessage, create_tracer, init_telemetry, traced_handler

__all__ = [
    # Logging
    "configure_logging",
    "get_console_logger",
    # Tracing
    "TracedMessage",
    "create_tracer",
    "init_telemetry",
    "traced_handler",
]