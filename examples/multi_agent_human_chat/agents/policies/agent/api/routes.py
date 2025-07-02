"""API routes for the Policies Agent."""

from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query

from agents.policies.agent.api.models import (
    CategoryStats,
    FullDocumentResponse,
    PolicyDocument,
    ReindexRequest,
    ReindexResponse,
    SearchResponse,
    VectorSearchRequest,
)
from agents.policies.agent.services.document_service import DocumentService
from agents.policies.agent.services.reindex_service import ReindexService
from agents.policies.agent.services.search_service import SearchService
from agents.policies.agent.tools.retrieval.full_document_retrieval import (
    get_document_chunk_range,
    retrieve_full_document_async,
)
from libraries.logger import get_console_logger

logger = get_console_logger("policies_api_routes")


def create_api_router(
    document_service: DocumentService,
    search_service: SearchService,
    reindex_service: ReindexService,
) -> APIRouter:
    """Create API router with all endpoints.
    
    Args:
        document_service: Document service instance
        search_service: Search service instance  
        reindex_service: Reindex service instance
        
    Returns:
        Configured APIRouter
    """
    router = APIRouter()

    @router.get("/health")
    async def health_check():
        """Health check endpoint."""
        return {"status": "healthy", "service": "policies-agent"}

    @router.get("/kb/documents", response_model=List[PolicyDocument])
    async def list_documents(
        category: Optional[str] = Query(None, description="Filter by category"),
        limit: int = Query(20, description="Number of documents to return", ge=1, le=100),
        offset: int = Query(0, description="Offset for pagination", ge=0),
    ):
        """
        List all documents in the knowledge base with optional category filter.

        - **category**: Optional category filter
        - **limit**: Number of documents to return
        - **offset**: Offset for pagination
        """
        try:
            documents = await document_service.list_documents(
                category=category,
                limit=limit,
                offset=offset
            )
            return documents
        except Exception as e:
            logger.error(f"List documents error: {e}")
            raise HTTPException(
                status_code=500, detail=f"Failed to list documents: {str(e)}"
            )

    @router.get("/kb/categories", response_model=List[CategoryStats])
    async def get_categories():
        """Get all available categories with document counts."""
        try:
            stats = await document_service.get_categories_stats()
            return [CategoryStats(**stat) for stat in stats]
        except Exception as e:
            logger.error(f"Get categories error: {e}")
            raise HTTPException(
                status_code=500, detail=f"Failed to get categories: {str(e)}"
            )

    @router.get("/kb/documents/{doc_id}", response_model=PolicyDocument)
    async def get_document(doc_id: str):
        """Get a specific document by ID."""
        try:
            document = await document_service.get_document_by_id(doc_id)
            
            if not document:
                raise HTTPException(
                    status_code=404, detail=f"Document not found: {doc_id}"
                )
            
            return document
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Get document error: {e}")
            raise HTTPException(
                status_code=500, detail=f"Failed to get document: {str(e)}"
            )

    @router.post("/kb/reindex", response_model=ReindexResponse)
    async def reindex_knowledge_base(request: ReindexRequest):
        """
        Re-index the knowledge base by clearing existing documents and re-ingesting.

        This endpoint will:
        1. Optionally clear all existing documents from Vespa
        2. Queue all policy documents for re-ingestion via Temporal
        3. Return the status of the operation

        Note: The actual ingestion happens asynchronously via Temporal workflows.
        """
        logger.info(
            f"Reindex request received: force_rebuild={request.force_rebuild}, "
            f"policy_ids={request.policy_ids}"
        )

        try:
            response = await reindex_service.reindex_documents(request)
            return response
        except Exception as e:
            logger.error(f"Reindex operation failed: {e}")
            raise HTTPException(
                status_code=500, detail=f"Reindex operation failed: {str(e)}"
            )

    @router.delete("/kb/clear")
    async def clear_index():
        """
        Clear all documents from the knowledge base.
        
        **WARNING**: This will delete all indexed documents. Use with caution.
        """
        try:
            result = await document_service.clear_all_documents()
            return result
        except Exception as e:
            logger.error(f"Clear index error: {e}")
            raise HTTPException(
                status_code=500, detail=f"Failed to clear index: {str(e)}"
            )

    @router.get("/kb/status")
    async def get_indexing_status():
        """
        Get the current indexing status of the knowledge base.
        
        Returns information about:
        - Whether the index contains documents
        - Total number of documents and chunks
        - Breakdown by category
        - Document-level statistics
        """
        try:
            status = await reindex_service.get_indexing_status()
            return status
        except Exception as e:
            logger.error(f"Get indexing status error: {e}")
            raise HTTPException(
                status_code=500, detail=f"Failed to get indexing status: {str(e)}"
            )

    @router.get("/kb/documents/{document_id}/full", response_model=FullDocumentResponse)
    async def get_full_document(document_id: str):
        """Get the full document by combining all its chunks."""
        try:
            full_doc = await retrieve_full_document_async(document_id)
            
            if not full_doc:
                raise HTTPException(
                    status_code=404, detail=f"Document not found: {document_id}"
                )
            
            return full_doc
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Get full document error: {e}")
            raise HTTPException(
                status_code=500, detail=f"Failed to get full document: {str(e)}"
            )

    @router.get("/kb/documents/{document_id}/range", response_model=FullDocumentResponse)
    async def get_document_range(
        document_id: str,
        start_chunk: int = Query(0, description="Starting chunk index", ge=0),
        end_chunk: Optional[int] = Query(None, description="Ending chunk index (inclusive)"),
    ):
        """Get a range of chunks from a document."""
        try:
            doc_range = await get_document_chunk_range(
                document_id, start_chunk, end_chunk
            )
            
            if not doc_range:
                raise HTTPException(
                    status_code=404,
                    detail=f"Document not found or invalid range: {document_id}",
                )
            
            return doc_range
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Get document range error: {e}")
            raise HTTPException(
                status_code=500, detail=f"Failed to get document range: {str(e)}"
            )

    @router.post("/kb/search/vector", response_model=SearchResponse)
    async def vector_search(request: VectorSearchRequest):
        """
        Perform semantic vector search on policy documents.
        
        Supports three search types:
        - **vector**: Pure semantic search using embeddings
        - **hybrid**: Combines vector and keyword search (recommended)
        - **keyword**: Traditional keyword search
        """
        try:
            result = await search_service.vector_search(request)
            
            return SearchResponse(
                query=result["query"],
                category=result["category"],
                total_hits=result["total_hits"],
                documents=result["documents"]
            )
        except Exception as e:
            logger.error(f"Vector search error: {e}")
            raise HTTPException(
                status_code=500, detail=f"Search failed: {str(e)}"
            )

    return router