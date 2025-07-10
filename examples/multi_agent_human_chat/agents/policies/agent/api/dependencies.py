from functools import lru_cache
from typing import Annotated

from fastapi import Depends
from sentence_transformers import SentenceTransformer

from agents.policies.agent.services.document_service import DocumentService
from agents.policies.agent.services.reindex_service import ReindexService
from agents.policies.agent.services.search_service import SearchService
from libraries.integrations.vespa import VespaClient
from libraries.observability.logger import get_console_logger

logger = get_console_logger("policies_api_dependencies")


@lru_cache()
def get_vespa_client() -> VespaClient:
    logger.info("Creating Vespa client instance")
    return VespaClient()


@lru_cache()
def get_embedding_model() -> SentenceTransformer:
    logger.info("Loading embedding model")
    return SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")


def get_document_service(
    vespa_client: Annotated[VespaClient, Depends(get_vespa_client)]
) -> DocumentService:
    return DocumentService(vespa_client)


def get_search_service(
    vespa_client: Annotated[VespaClient, Depends(get_vespa_client)],
    embedding_model: Annotated[SentenceTransformer, Depends(get_embedding_model)]
) -> SearchService:
    return SearchService(vespa_client, embedding_model)


def get_reindex_service(
    vespa_client: Annotated[VespaClient, Depends(get_vespa_client)]
) -> ReindexService:
    return ReindexService(vespa_client)