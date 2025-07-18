"""
Communication infrastructure for EggAI agents.

This module provides messaging, channels, and transport functionality.
"""

from .channels import channels
from .messaging import subscribe
from .transport import create_kafka_transport

__all__ = [
    "channels",
    "subscribe",
    "create_kafka_transport",
]