from __future__ import annotations

import os
from collections import defaultdict

from eggai import Agent, Channel
from eggai.transport import eggai_set_default_transport
from opentelemetry import trace

from libraries.kafka_transport import create_kafka_transport
from libraries.logger import get_console_logger
from libraries.tracing.init_metrics import init_token_metrics

from .config import settings
from .websocket_manager import WebSocketManager

logger = get_console_logger("frontend_agent")

# Load environment variable
GUARDRAILS_ENABLED = os.getenv("GUARDRAILS_TOKEN") is not None

if GUARDRAILS_ENABLED:
    try:
        from .guardrails import toxic_language_guard
    except ImportError as e:  # noqa: BLE001
        logger.error("Failed to import guardrails: %s", e)
        toxic_language_guard = None
else:
    logger.info("Guardrails disabled (no GUARDRAILS_TOKEN)")
    toxic_language_guard = None

# Set up Kafka transport
eggai_set_default_transport(
    lambda: create_kafka_transport(
        bootstrap_servers=settings.kafka_bootstrap_servers,
        ssl_cert=settings.kafka_ca_content,
    )
)

frontend_agent = Agent("FrontendAgent")
frontend_agent.logger = logger  # expose logger on the agent instance
human_channel = Channel("human")
human_stream_channel = Channel("human_stream")
websocket_manager = WebSocketManager()
messages_cache: defaultdict[str, list] = defaultdict(list)
tracer = trace.get_tracer("frontend_agent")

init_token_metrics(
    port=settings.prometheus_metrics_port, application_name=settings.app_name
)

# Import modules that register handlers after globals are defined
from . import handlers  # noqa: E402,F401
from .gateway import add_websocket_gateway  # noqa: E402

__all__ = [
    "frontend_agent",
    "add_websocket_gateway",
    "human_channel",
    "human_stream_channel",
]
