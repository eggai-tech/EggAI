import os
from contextlib import asynccontextmanager

import uvicorn
from eggai import eggai_cleanup
from eggai.transport import eggai_set_default_transport
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from agents.policies.agent.api.routes import router as api_router
from agents.policies.agent.config import settings
from libraries.communication.transport import create_kafka_transport
from libraries.ml.dspy.language_model import dspy_set_language_model
from libraries.observability.logger import get_console_logger
from libraries.observability.tracing import init_telemetry

eggai_set_default_transport(
    lambda: create_kafka_transport(
        bootstrap_servers=settings.kafka_bootstrap_servers,
        ssl_cert=settings.kafka_ca_content,
    )
)

from agents.policies.agent.agent import policies_agent

logger = get_console_logger("policies_agent")


@asynccontextmanager
async def lifespan(_: FastAPI):
    logger.info("Starting Policies Agent...")

    init_telemetry(app_name=settings.app_name, endpoint=settings.otel_endpoint)

    dspy_set_language_model(settings)

    logger.info("Starting agent...")
    await policies_agent.start()

    logger.info("Policies Agent started successfully")

    yield

    logger.info("Shutting down Policies Agent...")
    await eggai_cleanup()
    logger.info("Policies Agent shutdown complete")


app = FastAPI(
    title="Policies Agent API",
    description="API for querying and managing insurance policy documents",
    version="1.0.0",
    lifespan=lifespan,
)

# Add CORS middleware to allow cross-origin requests from the frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8000", "http://127.0.0.1:8000"],  # Frontend URLs
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api/v1", tags=["policies"])


if __name__ == "__main__":
    host = os.getenv("POLICIES_API_HOST", settings.api_host)
    port = int(os.getenv("POLICIES_API_PORT", settings.api_port))
    log_level = os.getenv("LOG_LEVEL", "info")
    uvicorn.run(
        "agents.policies.agent.main:app",
        host=host,
        port=port,
        reload=False,
        log_level=log_level,
    )
