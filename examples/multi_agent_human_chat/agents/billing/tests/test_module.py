from agents.billing.config import settings
from libraries.ml.dspy.language_model import dspy_set_language_model
from libraries.observability.logger import get_console_logger

logger = get_console_logger("billing_agent.tests.module")

# Configure language model based on settings with caching disabled for accuracy
dspy_lm = dspy_set_language_model(settings, overwrite_cache_enabled=False)