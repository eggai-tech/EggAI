"""Main module for the Policies Agent with FastAPI endpoints for Vespa knowledge base."""

from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional

import uvicorn
from eggai import eggai_cleanup
from eggai.transport import eggai_set_default_transport
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel

from agents.policies.agent.tools.retrieval.full_document_retrieval import (
    get_document_chunk_range,
    retrieve_full_document_async,
)
from agents.policies.config import settings
from agents.policies.embeddings import generate_embedding
from agents.policies.ingestion.documentation_temporal_client import (
    DocumentationTemporalClient,
)
from libraries.dspy_set_language_model import dspy_set_language_model
from libraries.kafka_transport import create_kafka_transport
from libraries.logger import get_console_logger
from libraries.tracing import init_telemetry
from libraries.vespa import VespaClient

eggai_set_default_transport(
    lambda: create_kafka_transport(
        bootstrap_servers=settings.kafka_bootstrap_servers,
        ssl_cert=settings.kafka_ca_content,
    )
)

# Import agent after transport is configured
from agents.policies.agent.agent import policies_agent

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


class FullDocumentResponse(BaseModel):
    """Full document response model."""

    document_id: str
    category: str
    source_file: str
    full_text: str
    total_chunks: int
    total_characters: int
    total_tokens: int
    headings: List[str]
    page_numbers: List[int]
    page_range: Optional[str]
    chunk_ids: List[str]
    metadata: Dict[str, Any]


class VectorSearchRequest(BaseModel):
    """Vector search request model."""

    query: str
    category: Optional[str] = None
    max_hits: int = 10
    search_type: str = "hybrid"  # "vector", "hybrid", or "keyword"
    alpha: float = 0.7  # Weight for hybrid search


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
    lifespan=lifespan,
)


@api.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "policies-agent"}


@api.get("/kb/documents", response_model=List[PolicyDocument])
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
        # Use an empty query to get all documents
        query = ""  # Empty query will match all documents

        # Get more results to handle pagination properly
        results = await vespa_client.search_documents(
            query=query,
            category=category,
            max_hits=limit + offset,  # Get enough results for pagination
        )

        # Apply pagination
        paginated_results = results[offset : offset + limit]

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
                chunk_position=result.get("chunk_position"),
            )
            documents.append(doc)

        return documents

    except Exception as e:
        logger.error(f"List documents error: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to list documents: {str(e)}"
        )


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
                max_hits=400,  # Use Vespa's configured limit
            )
            count = len(results)
            stats.append(CategoryStats(category=category, document_count=count))

        return stats

    except Exception as e:
        logger.error(f"Get categories error: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to get categories: {str(e)}"
        )


@api.get("/kb/document/{doc_id}")
async def get_document(doc_id: str):
    """
    Get a specific document by ID.
    """
    try:
        # Search for the specific document ID
        results = await vespa_client.search_documents(
            query=f'id:"{doc_id}"', max_hits=1
        )

        if not results:
            raise HTTPException(status_code=404, detail="Document not found")

        result = results[0]

        # Generate citation
        citation = None
        if result.get("page_range"):
            citation = (
                f"{result.get('source_file', 'Unknown')}, page {result['page_range']}"
            )

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
            chunk_position=result.get("chunk_position"),
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
    logger.info(
        f"Reindex request received: clear_existing={request.clear_existing}, "
        f"categories={request.categories}, force_rebuild={request.force_rebuild}"
    )

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
                    max_hits=400,  # Use Vespa's configured limit
                )
                documents_cleared = len(existing_results)

                # Clear the index by deleting all documents
                # Note: In production, you might want to use a more efficient bulk delete
                deleted_count = 0
                for doc in existing_results:
                    try:
                        # Delete document from Vespa using feed API
                        async with vespa_client.vespa_app.asyncio() as session:
                            # Use feed_data_point with empty fields to delete
                            response = await session.delete_data_point(
                                schema="policy_document", data_id=doc["id"]
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
                    config
                    for config in document_configs
                    if config["category"] in request.categories
                ]

            # Get base path for documents
            import os

            base_path = os.path.join(
                os.path.dirname(__file__), "ingestion", "documents"
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
                        force_rebuild=request.force_rebuild,
                    )

                    ingestion_results.append(
                        {
                            "file": config["file"],
                            "category": config["category"],
                            "workflow_id": result.workflow_id
                            if hasattr(result, "workflow_id")
                            else None,
                            "status": "queued",
                        }
                    )
                    documents_queued += 1

                    logger.info(f"Queued {config['file']} for ingestion")

                except Exception as e:
                    error_msg = f"Failed to queue {config['file']}: {str(e)}"
                    logger.error(error_msg)
                    errors.append(error_msg)

            # Prepare response
            if documents_queued > 0:
                status = "success" if not errors else "partial_success"
                message = (
                    f"Successfully queued {documents_queued} documents for re-indexing. "
                    f"{'Some errors occurred.' if errors else ''}"
                )
            else:
                status = "error"
                message = "No documents were queued for re-indexing."

            return ReindexResponse(
                status=status,
                message=message,
                documents_cleared=documents_cleared,
                documents_queued=documents_queued,
                errors=errors,
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
                errors=errors,
            )

    except Exception as e:
        logger.error(f"Reindex operation failed: {e}")
        return ReindexResponse(
            status="error", message=f"Re-indexing failed: {str(e)}", errors=[str(e)]
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
            max_hits=400,  # Use Vespa's configured limit
        )
        total_documents = len(existing_results)

        if total_documents == 0:
            return {
                "status": "success",
                "message": "Index is already empty",
                "documents_cleared": 0,
            }

        # Clear documents
        deleted_count = 0
        failed_count = 0

        for doc in existing_results:
            try:
                async with vespa_client.vespa_app.asyncio() as session:
                    # Use delete_data_point to delete document
                    response = await session.delete_data_point(
                        schema="policy_document", data_id=doc["id"]
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
            "failed_deletions": failed_count,
        }

    except Exception as e:
        logger.error(f"Failed to clear index: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to clear index: {str(e)}")


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
            max_hits=400,  # Use Vespa's configured limit
        )
        total_documents = len(all_results)

        # Get counts per category
        categories = ["auto", "home", "life", "health"]
        category_counts = {}

        for category in categories:
            cat_results = await vespa_client.search_documents(
                query="",
                category=category,
                max_hits=400,  # Use Vespa's configured limit
            )
            category_counts[category] = len(cat_results)

        # Try to get latest document timestamp
        latest_timestamp = None
        if all_results:
            # Sort by chunk_index descending to get the latest
            sorted_results = sorted(
                all_results, key=lambda x: x.get("chunk_index", 0), reverse=True
            )
            # In a real system, you'd store actual timestamps
            latest_timestamp = "Recently indexed"

        return {
            "status": "ok",
            "total_documents": total_documents,
            "documents_by_category": category_counts,
            "latest_indexing": latest_timestamp,
            "index_health": "healthy" if total_documents > 0 else "empty",
        }

    except Exception as e:
        logger.error(f"Failed to get indexing status: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to retrieve indexing status: {str(e)}"
        )


@api.get("/kb/full-document/{document_id}", response_model=FullDocumentResponse)
async def get_full_document(document_id: str):
    """
    Retrieve a complete document by reconstructing it from all its chunks.

    - **document_id**: The document identifier (e.g., "auto", "home", "life", "health")

    Returns the full document text and metadata.
    """
    try:
        result = await retrieve_full_document_async(document_id, vespa_client)

        if "error" in result:
            raise HTTPException(status_code=404, detail=result["error"])

        return FullDocumentResponse(**result)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get full document error: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to retrieve full document: {str(e)}"
        )


@api.get("/kb/document-range/{document_id}")
async def get_document_range(
    document_id: str,
    start_chunk: int = Query(..., description="Starting chunk index (0-based)"),
    end_chunk: Optional[int] = Query(
        None, description="Ending chunk index (inclusive)"
    ),
):
    """
    Retrieve a specific range of chunks from a document.

    - **document_id**: The document identifier
    - **start_chunk**: Starting chunk index (0-based)
    - **end_chunk**: Ending chunk index (inclusive), defaults to start_chunk if not provided
    """
    try:
        result = get_document_chunk_range(
            document_id, start_chunk, end_chunk, vespa_client
        )

        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get document range error: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to retrieve document range: {str(e)}"
        )


@api.post("/kb/search", response_model=SearchResponse)
async def vector_search(request: VectorSearchRequest):
    """
    Perform vector-based semantic search or hybrid search combining keyword and vector search.

    - **query**: The search query (will be converted to embedding)
    - **category**: Optional category filter
    - **max_hits**: Maximum number of results
    - **search_type**: Type of search ("vector", "hybrid", or "keyword")
    - **alpha**: Weight for hybrid search (0-1, higher = more vector influence)
    """
    try:
        # Validate search type
        valid_search_types = ["vector", "hybrid", "keyword"]
        if request.search_type not in valid_search_types:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid search type. Must be one of: {', '.join(valid_search_types)}",
            )

        # Generate embedding for the query
        query_embedding = generate_embedding(request.query)

        if not query_embedding:
            raise HTTPException(
                status_code=400, detail="Failed to generate embedding for query"
            )

        # Perform search based on type
        if request.search_type == "vector":
            # Pure vector search
            results = await vespa_client.vector_search(
                query_embedding=query_embedding,
                category=request.category,
                max_hits=request.max_hits,
            )
        elif request.search_type == "hybrid":
            # Hybrid search combining keyword and vector
            results = await vespa_client.hybrid_search(
                query=request.query,
                query_embedding=query_embedding,
                category=request.category,
                max_hits=request.max_hits,
                alpha=request.alpha,
            )
        else:
            # Regular keyword search
            results = await vespa_client.search_documents(
                query=request.query,
                category=request.category,
                max_hits=request.max_hits,
            )

        # Format results
        documents = []
        for result in results:
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
                page_numbers=result.get("page_numbers", []),
                page_range=result.get("page_range"),
                headings=result.get("headings", []),
                citation=citation,
                document_id=result.get("document_id"),
                previous_chunk_id=result.get("previous_chunk_id"),
                next_chunk_id=result.get("next_chunk_id"),
                chunk_position=result.get("chunk_position"),
            )
            documents.append(doc)

        return SearchResponse(
            query=request.query,
            category=request.category,
            total_hits=len(results),
            documents=documents,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Vector search error: {e}")
        raise HTTPException(status_code=500, detail=f"Vector search failed: {str(e)}")


if __name__ == "__main__":
    logger.info(f"Starting {settings.app_name} with FastAPI")

    # Always run with FastAPI and the agent together
    uvicorn.run(
        "agents.policies.agent.main:api",
        host="0.0.0.0",
        port=8002,  # Different port from frontend
        reload=False,  # Set to False for production
    )
