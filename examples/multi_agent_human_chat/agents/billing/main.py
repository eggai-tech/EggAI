from contextlib import asynccontextmanager

import uvicorn
from eggai import eggai_cleanup
from eggai.transport import eggai_set_default_transport
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from libraries.dspy_set_language_model import dspy_set_language_model
from libraries.kafka_transport import create_kafka_transport
from libraries.logger import get_console_logger
from libraries.tracing import init_telemetry

from .config import settings

eggai_set_default_transport(
    lambda: create_kafka_transport(
        bootstrap_servers=settings.kafka_bootstrap_servers,
        ssl_cert=settings.kafka_ca_content,
    )
)

from .agent import billing_agent

logger = get_console_logger("billing_agent")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle application lifecycle events."""
    logger.info(f"Starting {settings.app_name}...")
    
    init_telemetry(app_name=settings.app_name, endpoint=settings.otel_endpoint)
    dspy_set_language_model(settings)
    
    logger.info("Starting agent...")
    await billing_agent.start()
    
    logger.info(f"{settings.app_name} started successfully")
    
    yield
    
    logger.info(f"Shutting down {settings.app_name}...")
    billing_agent.stop()
    await eggai_cleanup()
    logger.info(f"{settings.app_name} shutdown complete")


# Import API routes from billing API
from agents.billing.api_main import (
    get_billing_record,
    get_billing_statistics,
    health_check,
    list_billing_records,
)

app = FastAPI(
    title="Billing Agent",
    description="Billing management agent with integrated API",
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
app.add_api_route("/api/v1/billing", list_billing_records, methods=["GET"])
app.add_api_route("/api/v1/billing/stats", get_billing_statistics, methods=["GET"])
app.add_api_route("/api/v1/billing/{policy_number}", get_billing_record, methods=["GET"])



if __name__ == "__main__":
    uvicorn.run(
        "agents.billing.main:app",
        host="0.0.0.0",
        port=8004,
        reload=False,
        log_level="info",
    )
