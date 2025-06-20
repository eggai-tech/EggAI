"""Vespa integration library for EggAI."""

from .config import VespaConfig
from .schemas import PolicyDocument
from .vespa_client import VespaClient

__all__ = ["VespaClient", "VespaConfig", "PolicyDocument"]