"""Tests for the billing DSPy module without agent integration."""



from agents.billing.config import settings
from libraries.dspy_set_language_model import dspy_set_language_model
from libraries.logger import get_console_logger

logger = get_console_logger("billing_agent.tests.module")

# Configure language model based on settings with caching disabled for accuracy
dspy_lm = dspy_set_language_model(settings, overwrite_cache_enabled=False)


# Note: The actual DSPy streaming test has been moved to test_module_fixed.py
# to avoid issues with DSPy's complex streaming implementation in test environments.