from __future__ import annotations

import os
from typing import List, Optional

from fastapi import APIRouter, HTTPException

from agents.policies.agent.models import CategoryStats, ReindexRequest, ReindexResponse
from agents.policies.agent.routes import vespa_client
from agents.policies.ingestion.documentation_temporal_client import (
    DocumentationTemporalClient,
)
from libraries.logger import get_console_logger

router = APIRouter()
logger = get_console_logger("policies_agent")


@router.post("/kb/reindex", response_model=ReindexResponse)
async def reindex_knowledge_base(request: ReindexRequest) -> ReindexResponse:
    """Re-index the knowledge base by clearing and re-ingesting documents."""
    logger.info(
        "Reindex request received: clear_existing=%s, categories=%s, force_rebuild=%s",
        request.clear_existing,
        request.categories,
        request.force_rebuild,
    )
    errors: List[str] = []
    documents_cleared: Optional[int] = None
    try:
        if request.clear_existing:
            try:
                logger.info("Clearing existing documents from Vespa...")
                existing_results = await vespa_client.search_documents(query="", max_hits=400)
                documents_cleared = len(existing_results)
                deleted_count = 0
                for doc in existing_results:
                    try:
                        async with vespa_client.vespa_app.asyncio() as session:
                            await session.delete_data_point(schema="policy_document", data_id=doc["id"])
                        deleted_count += 1
                    except Exception as exc:  # noqa: BLE001
                        logger.warning("Failed to delete document %s: %s", doc["id"], exc)
                logger.info("Cleared %s documents from Vespa", deleted_count)
            except Exception as exc:  # noqa: BLE001
                error_msg = f"Failed to clear existing documents: {exc}"
                logger.error(error_msg)
                errors.append(error_msg)
        try:
            temporal_client = DocumentationTemporalClient()
            document_configs = [
                {"file": "auto.md", "category": "auto"},
                {"file": "home.md", "category": "home"},
                {"file": "life.md", "category": "life"},
                {"file": "health.md", "category": "health"},
            ]
            if request.categories:
                document_configs = [
                    cfg for cfg in document_configs if cfg["category"] in request.categories
                ]
            base_path = os.path.join(os.path.dirname(__file__), "ingestion", "documents")
            documents_queued = 0
            for cfg in document_configs:
                file_path = os.path.join(base_path, cfg["file"])
                if not os.path.exists(file_path):
                    error_msg = f"Document not found: {file_path}"
                    logger.warning(error_msg)
                    errors.append(error_msg)
                    continue
                try:
                    result = await temporal_client.ingest_document_async(
                        file_path=file_path,
                        category=cfg["category"],
                        force_rebuild=request.force_rebuild,
                    )
                    documents_queued += 1
                    logger.info("Queued %s for ingestion", cfg["file"])
                except Exception as exc:  # noqa: BLE001
                    error_msg = f"Failed to queue {cfg['file']}: {exc}"
                    logger.error(error_msg)
                    errors.append(error_msg)
            status = "success" if documents_queued and not errors else "partial_success" if documents_queued else "error"
            message = (
                f"Successfully queued {documents_queued} documents for re-indexing."
                if documents_queued
                else "No documents were queued for re-indexing."
            )
            if errors:
                message += " Some errors occurred."
            return ReindexResponse(
                status=status,
                message=message,
                documents_cleared=documents_cleared,
                documents_queued=documents_queued,
                errors=errors,
            )
        except Exception as exc:  # noqa: BLE001
            error_msg = f"Failed to queue documents for ingestion: {exc}"
            logger.error(error_msg)
            errors.append(error_msg)
            return ReindexResponse(
                status="error",
                message="Failed to initiate re-indexing process",
                documents_cleared=documents_cleared,
                documents_queued=0,
                errors=errors,
            )
    except Exception as exc:  # noqa: BLE001
        logger.error("Reindex operation failed: %s", exc)
        return ReindexResponse(status="error", message=f"Re-indexing failed: {exc}", errors=[str(exc)])


@router.delete("/kb/clear-index")
async def clear_index():
    """Remove all documents from the Vespa index."""
    try:
        logger.info("Clear index request received")
        existing_results = await vespa_client.search_documents(query="", max_hits=400)
        total_documents = len(existing_results)
        if total_documents == 0:
            return {"status": "success", "message": "Index is already empty", "documents_cleared": 0}
        deleted_count = 0
        failed_count = 0
        for doc in existing_results:
            try:
                async with vespa_client.vespa_app.asyncio() as session:
                    await session.delete_data_point(schema="policy_document", data_id=doc["id"])
                deleted_count += 1
            except Exception as exc:  # noqa: BLE001
                logger.warning("Failed to delete document %s: %s", doc["id"], exc)
                failed_count += 1
        logger.info("Cleared %s documents from Vespa", deleted_count)
        return {
            "status": "success" if failed_count == 0 else "partial_success",
            "message": f"Cleared {deleted_count} documents from index",
            "documents_cleared": deleted_count,
            "failed_deletions": failed_count,
        }
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to clear index: %s", exc)
        raise HTTPException(status_code=500, detail=f"Failed to clear index: {exc}")


@router.get("/kb/indexing-status")
async def get_indexing_status():
    """Return the current status of the indexing process."""
    try:
        all_results = await vespa_client.search_documents(query="", max_hits=400)
        total_documents = len(all_results)
        categories = ["auto", "home", "life", "health"]
        category_counts = {}
        for category in categories:
            cat_results = await vespa_client.search_documents(query="", category=category, max_hits=400)
            category_counts[category] = len(cat_results)
        latest_timestamp = "Recently indexed" if all_results else None
        return {
            "status": "ok",
            "total_documents": total_documents,
            "documents_by_category": category_counts,
            "latest_indexing": latest_timestamp,
            "index_health": "healthy" if total_documents > 0 else "empty",
        }
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to get indexing status: %s", exc)
        raise HTTPException(status_code=500, detail=f"Failed to retrieve indexing status: {exc}")


@router.get("/kb/categories", response_model=List[CategoryStats])
async def get_categories() -> List[CategoryStats]:
    """Get statistics about documents per category."""
    try:
        categories = ["auto", "home", "life", "health"]
        stats = []
        for category in categories:
            results = await vespa_client.search_documents(query="", category=category, max_hits=400)
            stats.append(CategoryStats(category=category, document_count=len(results)))
        return stats
    except Exception as exc:  # noqa: BLE001
        logger.error("Get categories error: %s", exc)
        raise HTTPException(status_code=500, detail=f"Failed to get categories: {exc}")
