"""Dependency injection for the Policies Agent API."""

from functools import lru_cache
from typing import Annotated

from fastapi import Depends
from sentence_transformers import SentenceTransformer

from agents.policies.agent.services.document_service import DocumentService
from agents.policies.agent.services.reindex_service import ReindexService
from agents.policies.agent.services.search_service import SearchService
from libraries.logger import get_console_logger
from libraries.vespa import VespaClient

logger = get_console_logger("policies_api_dependencies")


@lru_cache()
def get_vespa_client() -> VespaClient:
    """Get Vespa client instance.
    
    Uses lru_cache to ensure we only create one instance per process.
    
    Returns:
        VespaClient instance
    """
    logger.info("Creating Vespa client instance")
    return VespaClient()


@lru_cache()
def get_embedding_model() -> SentenceTransformer:
    """Get embedding model instance.
    
    Uses lru_cache to ensure we only load the model once per process.
    
    Returns:
        SentenceTransformer instance
    """
    logger.info("Loading embedding model")
    return SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")


def get_document_service(
    vespa_client: Annotated[VespaClient, Depends(get_vespa_client)]
) -> DocumentService:
    """Get document service instance with dependencies injected.
    
    Args:
        vespa_client: Injected Vespa client
        
    Returns:
        DocumentService instance
    """
    return DocumentService(vespa_client)


def get_search_service(
    vespa_client: Annotated[VespaClient, Depends(get_vespa_client)],
    embedding_model: Annotated[SentenceTransformer, Depends(get_embedding_model)]
) -> SearchService:
    """Get search service instance with dependencies injected.
    
    Args:
        vespa_client: Injected Vespa client
        embedding_model: Injected embedding model
        
    Returns:
        SearchService instance
    """
    return SearchService(vespa_client, embedding_model)


def get_reindex_service(
    vespa_client: Annotated[VespaClient, Depends(get_vespa_client)]
) -> ReindexService:
    """Get reindex service instance with dependencies injected.
    
    Args:
        vespa_client: Injected Vespa client
        
    Returns:
        ReindexService instance
    """
    return ReindexService(vespa_client)