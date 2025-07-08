"""
EggAI Libraries - Organized utilities for building AI agents.

Structure:
- core/: Core utilities and base classes
- communication/: Messaging, channels, and transport
- ml/: Machine learning utilities and DSPy integration  
- observability/: Logging, tracing, and monitoring
- integrations/: External service integrations
- testing/: Test utilities and unit tests

Import from specific modules:
  from libraries.communication import channels, subscribe
  from libraries.core import BaseAgentConfig
  from libraries.observability import get_console_logger
"""

from libraries.core.patches import patch_usage_tracker

# Apply patches
patch_usage_tracker()
