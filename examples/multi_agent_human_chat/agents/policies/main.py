"""Main module for the Policies Agent with FastAPI endpoints for Vespa knowledge base."""

from contextlib import asynccontextmanager
from typing import List, Optional

import uvicorn
from eggai import eggai_cleanup
from eggai.transport import eggai_set_default_transport
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel

from libraries.dspy_set_language_model import dspy_set_language_model
from libraries.kafka_transport import create_kafka_transport
from libraries.logger import get_console_logger
from libraries.tracing import init_telemetry
from libraries.vespa import VespaClient

from .config import settings
from .ingestion.documentation_temporal_client import DocumentationTemporalClient

eggai_set_default_transport(
    lambda: create_kafka_transport(
        bootstrap_servers=settings.kafka_bootstrap_servers,
        ssl_cert=settings.kafka_ca_content,
    )
)

# Import agent after transport is configured
from .agent import policies_agent

logger = get_console_logger("policies_agent")

# Initialize Vespa client for API endpoints
vespa_client = VespaClient()

# Response models
class PolicyDocument(BaseModel):
    """Policy document model for API responses."""
    id: str
    title: str
    text: str
    category: str
    chunk_index: int
    source_file: str
    relevance: Optional[float] = None
    
    # Enhanced metadata fields
    page_numbers: List[int] = []
    page_range: Optional[str] = None
    headings: List[str] = []
    citation: Optional[str] = None
    
    # Relationships
    document_id: Optional[str] = None
    previous_chunk_id: Optional[str] = None
    next_chunk_id: Optional[str] = None
    chunk_position: Optional[float] = None


class SearchResponse(BaseModel):
    """Search response model."""
    query: str
    category: Optional[str]
    total_hits: int
    documents: List[PolicyDocument]


class CategoryStats(BaseModel):
    """Category statistics model."""
    category: str
    document_count: int


class ReindexRequest(BaseModel):
    """Request model for reindexing operation."""
    clear_existing: bool = True
    categories: Optional[List[str]] = None
    force_rebuild: bool = True


class ReindexResponse(BaseModel):
    """Response model for reindexing operation."""
    status: str
    message: str
    documents_cleared: Optional[int] = None
    documents_queued: int = 0
    errors: List[str] = []


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle."""
    try:
        # Initialize telemetry and language model
        init_telemetry(app_name=settings.app_name, endpoint=settings.otel_endpoint)
        dspy_set_language_model(settings)
        
        # Start the agent
        await policies_agent.start()
        logger.info(f"{settings.app_name} started successfully")
        
        yield
    finally:
        logger.info("Cleaning up resources")
        await eggai_cleanup()


# Create FastAPI app
api = FastAPI(
    title="Policies Agent Knowledge Base API",
    description="Browse and search the Vespa policy documents knowledge base",
    version="1.0.0",
    lifespan=lifespan
)


@api.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "policies-agent"}


@api.get("/kb/search", response_model=SearchResponse)
async def search_knowledge_base(
    query: str = Query(..., description="Search query"),
    category: Optional[str] = Query(None, description="Filter by category (auto, home, life, health)"),
    max_hits: int = Query(10, description="Maximum number of results", ge=1, le=100)
):
    """
    Search the policy documents knowledge base.
    
    - **query**: The search query string
    - **category**: Optional category filter (auto, home, life, health)
    - **max_hits**: Maximum number of results to return (1-100)
    """
    try:
        # Validate category if provided
        valid_categories = ["auto", "home", "life", "health"]
        if category and category not in valid_categories:
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid category. Must be one of: {', '.join(valid_categories)}"
            )
        
        # Search documents (await the async method)
        results = await vespa_client.search_documents(
            query=query,
            category=category,
            max_hits=max_hits
        )
        
        # Format results (search_documents returns a list of dicts)
        documents = []
        for result in results:
            # Generate citation
            citation = None
            if result.get("page_range"):
                citation = f"{result.get('source_file', 'Unknown')}, page {result['page_range']}"
            
            doc = PolicyDocument(
                id=result.get("id", ""),
                title=result.get("title", ""),
                text=result.get("text", ""),
                category=result.get("category", ""),
                chunk_index=result.get("chunk_index", 0),
                source_file=result.get("source_file", ""),
                relevance=result.get("relevance", 0.0),
                # Enhanced metadata
                page_numbers=result.get("page_numbers", []),
                page_range=result.get("page_range"),
                headings=result.get("headings", []),
                citation=citation,
                # Relationships
                document_id=result.get("document_id"),
                previous_chunk_id=result.get("previous_chunk_id"),
                next_chunk_id=result.get("next_chunk_id"),
                chunk_position=result.get("chunk_position")
            )
            documents.append(doc)
        
        return SearchResponse(
            query=query,
            category=category,
            total_hits=len(results),
            documents=documents
        )
        
    except Exception as e:
        logger.error(f"Search error: {e}")
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


@api.get("/kb/documents", response_model=List[PolicyDocument])
async def list_documents(
    category: Optional[str] = Query(None, description="Filter by category"),
    limit: int = Query(20, description="Number of documents to return", ge=1, le=100),
    offset: int = Query(0, description="Offset for pagination", ge=0)
):
    """
    List all documents in the knowledge base with optional category filter.
    
    - **category**: Optional category filter
    - **limit**: Number of documents to return
    - **offset**: Offset for pagination
    """
    try:
        # Use an empty query to get all documents
        query = ""  # Empty query will match all documents
        
        # Get more results to handle pagination properly
        results = await vespa_client.search_documents(
            query=query,
            category=category,
            max_hits=limit + offset  # Get enough results for pagination
        )
        
        # Apply pagination
        paginated_results = results[offset:offset+limit]
        
        documents = []
        for result in paginated_results:
            # Generate citation
            citation = None
            if result.get("page_range"):
                citation = f"{result.get('source_file', 'Unknown')}, page {result['page_range']}"
            
            doc = PolicyDocument(
                id=result.get("id", ""),
                title=result.get("title", ""),
                text=result.get("text", ""),
                category=result.get("category", ""),
                chunk_index=result.get("chunk_index", 0),
                source_file=result.get("source_file", ""),
                # Enhanced metadata
                page_numbers=result.get("page_numbers", []),
                page_range=result.get("page_range"),
                headings=result.get("headings", []),
                citation=citation,
                # Relationships
                document_id=result.get("document_id"),
                previous_chunk_id=result.get("previous_chunk_id"),
                next_chunk_id=result.get("next_chunk_id"),
                chunk_position=result.get("chunk_position")
            )
            documents.append(doc)
        
        return documents
        
    except Exception as e:
        logger.error(f"List documents error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list documents: {str(e)}")


@api.get("/kb/categories", response_model=List[CategoryStats])
async def get_categories():
    """
    Get statistics about documents per category.
    """
    try:
        categories = ["auto", "home", "life", "health"]
        stats = []
        
        for category in categories:
            results = await vespa_client.search_documents(
                query="",  # Empty query to get all documents
                category=category,
                max_hits=400  # Use Vespa's configured limit
            )
            count = len(results)
            stats.append(CategoryStats(category=category, document_count=count))
        
        return stats
        
    except Exception as e:
        logger.error(f"Get categories error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get categories: {str(e)}")


@api.get("/kb/document/{doc_id}")
async def get_document(doc_id: str):
    """
    Get a specific document by ID.
    """
    try:
        # Search for the specific document ID
        results = await vespa_client.search_documents(
            query=f'id:"{doc_id}"',
            max_hits=1
        )
        
        if not results:
            raise HTTPException(status_code=404, detail="Document not found")
        
        result = results[0]
        
        # Generate citation
        citation = None
        if result.get("page_range"):
            citation = f"{result.get('source_file', 'Unknown')}, page {result['page_range']}"
        
        return PolicyDocument(
            id=result.get("id", ""),
            title=result.get("title", ""),
            text=result.get("text", ""),
            category=result.get("category", ""),
            chunk_index=result.get("chunk_index", 0),
            source_file=result.get("source_file", ""),
            # Enhanced metadata
            page_numbers=result.get("page_numbers", []),
            page_range=result.get("page_range"),
            headings=result.get("headings", []),
            citation=citation,
            # Relationships
            document_id=result.get("document_id"),
            previous_chunk_id=result.get("previous_chunk_id"),
            next_chunk_id=result.get("next_chunk_id"),
            chunk_position=result.get("chunk_position")
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get document error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get document: {str(e)}")


@api.post("/kb/reindex", response_model=ReindexResponse)
async def reindex_knowledge_base(request: ReindexRequest):
    """
    Re-index the knowledge base by clearing existing documents and re-ingesting.
    
    This endpoint will:
    1. Optionally clear all existing documents from Vespa
    2. Queue all policy documents for re-ingestion via Temporal
    3. Return the status of the operation
    
    Note: The actual ingestion happens asynchronously via Temporal workflows.
    """
    logger.info(f"Reindex request received: clear_existing={request.clear_existing}, "
                f"categories={request.categories}, force_rebuild={request.force_rebuild}")
    
    errors = []
    documents_cleared = None
    
    try:
        # Step 1: Clear existing documents if requested
        if request.clear_existing:
            try:
                logger.info("Clearing existing documents from Vespa...")
                
                # Get count of existing documents first
                existing_results = await vespa_client.search_documents(
                    query="",
                    max_hits=400  # Use Vespa's configured limit
                )
                documents_cleared = len(existing_results)
                
                # Clear the index by deleting all documents
                # Note: In production, you might want to use a more efficient bulk delete
                deleted_count = 0
                for doc in existing_results:
                    try:
                        # Delete document from Vespa
                        async with vespa_client.vespa_app.asyncio() as session:
                            await session.delete(
                                schema="policy_document",
                                id=doc["id"]
                            )
                        deleted_count += 1
                    except Exception as e:
                        logger.warning(f"Failed to delete document {doc['id']}: {e}")
                
                logger.info(f"Cleared {deleted_count} documents from Vespa")
                
            except Exception as e:
                error_msg = f"Failed to clear existing documents: {str(e)}"
                logger.error(error_msg)
                errors.append(error_msg)
        
        # Step 2: Queue documents for re-ingestion
        try:
            # Initialize Temporal client
            temporal_client = DocumentationTemporalClient()
            
            # Define document paths and their categories
            document_configs = [
                {"file": "auto.md", "category": "auto"},
                {"file": "home.md", "category": "home"},
                {"file": "life.md", "category": "life"},
                {"file": "health.md", "category": "health"},
            ]
            
            # Filter by categories if specified
            if request.categories:
                document_configs = [
                    config for config in document_configs 
                    if config["category"] in request.categories
                ]
            
            # Get base path for documents
            import os
            base_path = os.path.join(
                os.path.dirname(__file__),
                "ingestion",
                "documents"
            )
            
            # Queue each document for ingestion
            documents_queued = 0
            ingestion_results = []
            
            for config in document_configs:
                file_path = os.path.join(base_path, config["file"])
                
                if not os.path.exists(file_path):
                    error_msg = f"Document not found: {file_path}"
                    logger.warning(error_msg)
                    errors.append(error_msg)
                    continue
                
                try:
                    # Start ingestion workflow
                    result = await temporal_client.ingest_document_async(
                        file_path=file_path,
                        category=config["category"],
                        force_rebuild=request.force_rebuild
                    )
                    
                    ingestion_results.append({
                        "file": config["file"],
                        "category": config["category"],
                        "workflow_id": result.workflow_id if hasattr(result, 'workflow_id') else None,
                        "status": "queued"
                    })
                    documents_queued += 1
                    
                    logger.info(f"Queued {config['file']} for ingestion")
                    
                except Exception as e:
                    error_msg = f"Failed to queue {config['file']}: {str(e)}"
                    logger.error(error_msg)
                    errors.append(error_msg)
            
            # Prepare response
            if documents_queued > 0:
                status = "success" if not errors else "partial_success"
                message = (f"Successfully queued {documents_queued} documents for re-indexing. "
                          f"{'Some errors occurred.' if errors else ''}")
            else:
                status = "error"
                message = "No documents were queued for re-indexing."
            
            return ReindexResponse(
                status=status,
                message=message,
                documents_cleared=documents_cleared,
                documents_queued=documents_queued,
                errors=errors
            )
            
        except Exception as e:
            error_msg = f"Failed to queue documents for ingestion: {str(e)}"
            logger.error(error_msg)
            errors.append(error_msg)
            
            return ReindexResponse(
                status="error",
                message="Failed to initiate re-indexing process",
                documents_cleared=documents_cleared,
                documents_queued=0,
                errors=errors
            )
            
    except Exception as e:
        logger.error(f"Reindex operation failed: {e}")
        return ReindexResponse(
            status="error",
            message=f"Re-indexing failed: {str(e)}",
            errors=[str(e)]
        )


@api.delete("/kb/clear-index")
async def clear_index():
    """
    Clear all documents from the Vespa index.
    
    This is a destructive operation that removes all indexed documents.
    Use the /kb/reindex endpoint to clear and re-index in one operation.
    """
    try:
        logger.info("Clear index request received")
        
        # Get count of existing documents
        existing_results = await vespa_client.search_documents(
            query="",
            max_hits=400  # Use Vespa's configured limit
        )
        total_documents = len(existing_results)
        
        if total_documents == 0:
            return {
                "status": "success",
                "message": "Index is already empty",
                "documents_cleared": 0
            }
        
        # Clear documents
        deleted_count = 0
        failed_count = 0
        
        for doc in existing_results:
            try:
                async with vespa_client.vespa_app.asyncio() as session:
                    await session.delete(
                        schema="policy_document",
                        id=doc["id"]
                    )
                deleted_count += 1
            except Exception as e:
                logger.warning(f"Failed to delete document {doc['id']}: {e}")
                failed_count += 1
        
        logger.info(f"Cleared {deleted_count} documents from Vespa")
        
        return {
            "status": "success" if failed_count == 0 else "partial_success",
            "message": f"Cleared {deleted_count} documents from index",
            "documents_cleared": deleted_count,
            "failed_deletions": failed_count
        }
        
    except Exception as e:
        logger.error(f"Failed to clear index: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to clear index: {str(e)}"
        )


@api.get("/kb/indexing-status")
async def get_indexing_status():
    """
    Get the current status of the indexing process.
    
    This endpoint provides information about:
    - Total documents in the index
    - Documents per category
    - Last indexing timestamp (if available)
    """
    try:
        # Get total document count
        all_results = await vespa_client.search_documents(
            query="",
            max_hits=400  # Use Vespa's configured limit
        )
        total_documents = len(all_results)
        
        # Get counts per category
        categories = ["auto", "home", "life", "health"]
        category_counts = {}
        
        for category in categories:
            cat_results = await vespa_client.search_documents(
                query="",
                category=category,
                max_hits=400  # Use Vespa's configured limit
            )
            category_counts[category] = len(cat_results)
        
        # Try to get latest document timestamp
        latest_timestamp = None
        if all_results:
            # Sort by chunk_index descending to get the latest
            sorted_results = sorted(
                all_results, 
                key=lambda x: x.get("chunk_index", 0), 
                reverse=True
            )
            # In a real system, you'd store actual timestamps
            latest_timestamp = "Recently indexed"
        
        return {
            "status": "ok",
            "total_documents": total_documents,
            "documents_by_category": category_counts,
            "latest_indexing": latest_timestamp,
            "index_health": "healthy" if total_documents > 0 else "empty"
        }
        
    except Exception as e:
        logger.error(f"Failed to get indexing status: {e}")
        raise HTTPException(
            status_code=500, 
            detail=f"Failed to retrieve indexing status: {str(e)}"
        )


if __name__ == "__main__":
    logger.info(f"Starting {settings.app_name} with FastAPI")
    
    # Always run with FastAPI and the agent together
    uvicorn.run(
        "agents.policies.main:api",
        host="0.0.0.0",
        port=8002,  # Different port from frontend
        reload=False  # Set to False for production
    )