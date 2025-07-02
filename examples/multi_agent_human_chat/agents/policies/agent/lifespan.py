from contextlib import asynccontextmanager

from eggai import eggai_cleanup
from fastapi import FastAPI

from agents.policies.agent.agent import policies_agent
from agents.policies.config import settings
from libraries.dspy_set_language_model import dspy_set_language_model
from libraries.logger import get_console_logger
from libraries.tracing import init_telemetry

logger = get_console_logger("policies_agent")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle."""
    try:
        init_telemetry(app_name=settings.app_name, endpoint=settings.otel_endpoint)
        dspy_set_language_model(settings)
        await policies_agent.start()
        logger.info(f"{settings.app_name} started successfully")
        yield
    finally:
        logger.info("Cleaning up resources")
        await eggai_cleanup()
