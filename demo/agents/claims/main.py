from contextlib import asynccontextmanager

import uvicorn
from eggai import eggai_cleanup
from eggai.transport import eggai_set_default_transport
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from libraries.communication.transport import create_kafka_transport
from libraries.ml.dspy.language_model import dspy_set_language_model
from libraries.observability.logger import get_console_logger
from libraries.observability.tracing import init_telemetry

from .config import settings

eggai_set_default_transport(
    lambda: create_kafka_transport(
        bootstrap_servers=settings.kafka_bootstrap_servers,
        ssl_cert=settings.kafka_ca_content,
    )
)

from .agent import claims_agent

logger = get_console_logger("claims_agent")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle application lifecycle events."""
    logger.info(f"Starting {settings.app_name}...")
    
    init_telemetry(app_name=settings.app_name, endpoint=settings.otel_endpoint)
    dspy_set_language_model(settings)
    
    from agents.claims.dspy_modules.claims import load_optimized_prompts
    load_optimized_prompts()
    
    logger.info("Starting agent...")
    await claims_agent.start()
    
    logger.info(f"{settings.app_name} started successfully")
    
    yield
    
    logger.info(f"Shutting down {settings.app_name}...")
    claims_agent.stop()
    await eggai_cleanup()
    logger.info(f"{settings.app_name} shutdown complete")


# Import API routes from claims API
from agents.claims.api_main import (
    get_claim,
    get_claims_statistics,
    health_check,
    list_claims,
)

app = FastAPI(
    title="Claims Agent",
    description="Claims processing agent with integrated API",
    version="1.0.0",
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8000", "http://127.0.0.1:8000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add the API routes directly
# Note: Order matters - more specific routes should come before parameterized routes
app.add_api_route("/health", health_check, methods=["GET"])
app.add_api_route("/api/v1/claims", list_claims, methods=["GET"])
app.add_api_route("/api/v1/claims/stats", get_claims_statistics, methods=["GET"])
app.add_api_route("/api/v1/claims/{claim_number}", get_claim, methods=["GET"])


if __name__ == "__main__":
    uvicorn.run(
        "agents.claims.main:app",
        host="0.0.0.0",
        port=8003,
        reload=False,
        log_level="info",
    )
