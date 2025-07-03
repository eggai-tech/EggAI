"""Main module for the Policies Agent with FastAPI endpoints."""

from contextlib import asynccontextmanager

import uvicorn
from eggai import eggai_cleanup
from eggai.transport import eggai_set_default_transport
from fastapi import FastAPI

from agents.policies.agent.api.routes import router as api_router
from agents.policies.config import settings
from libraries.dspy_set_language_model import dspy_set_language_model
from libraries.kafka_transport import create_kafka_transport
from libraries.logger import get_console_logger
from libraries.tracing import init_telemetry

# Configure transport before importing agent
eggai_set_default_transport(
    lambda: create_kafka_transport(
        bootstrap_servers=settings.kafka_bootstrap_servers,
        ssl_cert=settings.kafka_ca_content,
    )
)

# Import agent after transport is configured
from agents.policies.agent.agent import policies_agent

logger = get_console_logger("policies_agent")



@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle application lifecycle events."""
    # Startup
    logger.info("Starting Policies Agent...")
    
    # Initialize telemetry
    init_telemetry(app_name=settings.app_name, endpoint=settings.otel_endpoint)
    
    # Set up DSPy LM
    dspy_set_language_model(settings)
    
    # Start the agent
    logger.info("Starting agent...")
    await policies_agent.start()
    
    logger.info("Policies Agent started successfully")
    
    yield
    
    # Shutdown
    logger.info("Shutting down Policies Agent...")
    policies_agent.stop()
    await eggai_cleanup()
    logger.info("Policies Agent shutdown complete")


# Create FastAPI app
app = FastAPI(
    title="Policies Agent API",
    description="API for querying and managing insurance policy documents",
    version="1.0.0",
    lifespan=lifespan,
)

# Include API router
app.include_router(api_router, prefix="/api/v1", tags=["policies"])


if __name__ == "__main__":
    uvicorn.run(
        "agents.policies.agent.main:app",
        host="0.0.0.0",
        port=8002,
        reload=False,
        log_level="info",
    )