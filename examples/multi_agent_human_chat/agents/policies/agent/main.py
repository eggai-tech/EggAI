"""FastAPI application for the Policies agent."""

from fastapi import FastAPI

from .lifespan import lifespan
from .routes import documents, indexing, search
from .transport import configure_transport

configure_transport()

api = FastAPI(
    title="Policies Agent Knowledge Base API",
    description="Browse and search the Vespa policy documents knowledge base",
    version="1.0.0",
    lifespan=lifespan,
)

api.include_router(documents.router)
api.include_router(search.router)
api.include_router(indexing.router)


@api.get("/health")
async def health_check() -> dict[str, str]:
    """Simple health check endpoint."""
    return {"status": "healthy", "service": "policies-agent"}
