from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile

from agents.policies.agent.api.dependencies import (
    get_document_service,
    get_reindex_service,
    get_search_service,
)
from agents.policies.agent.api.models import (
    CategoryStats,
    FullDocumentResponse,
    PersonalPolicy,
    PolicyDocument,
    PolicyListResponse,
    ReindexRequest,
    ReindexResponse,
    SearchRequest,
    SearchResponse,
)
from agents.policies.agent.api.validators import (
    validate_category,
    validate_document_id,
    validate_query,
)
from agents.policies.agent.services.document_service import DocumentService
from agents.policies.agent.services.reindex_service import ReindexService
from agents.policies.agent.services.search_service import SearchService
from agents.policies.agent.tools.retrieval.full_document_retrieval import (
    get_document_chunk_range,
    retrieve_full_document_async,
)
from libraries.observability.logger import get_console_logger

logger = get_console_logger("policies_api_routes")

# Create the router
router = APIRouter()


@router.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "policies-agent", "version": "1.0.0"}


@router.get("/kb/documents", response_model=List[PolicyDocument])
async def list_documents(
    category: Optional[str] = Query(None, description="Filter by category"),
    limit: int = Query(20, description="Number of documents to return", ge=1, le=100),
    offset: int = Query(0, description="Offset for pagination", ge=0),
    document_service: DocumentService = Depends(get_document_service),
):
    """
    List all documents in the knowledge base with optional category filter.

    - **category**: Optional category filter
    - **limit**: Number of documents to return
    - **offset**: Offset for pagination
    """
    try:
        # Validate category if provided
        validated_category = validate_category(category)
        
        documents = await document_service.list_documents(
            category=validated_category,
            limit=limit,
            offset=offset
        )
        return documents
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"List documents error: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail="Internal server error while listing documents"
        )


@router.get("/kb/categories", response_model=List[CategoryStats])
async def get_categories(
    document_service: DocumentService = Depends(get_document_service),
):
    """Get all available categories with document counts."""
    try:
        stats = await document_service.get_categories_stats()
        return [CategoryStats(**stat) for stat in stats]
    except Exception as e:
        logger.error(f"Get categories error: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail="Internal server error while retrieving categories"
        )


@router.get("/kb/documents/{doc_id}", response_model=PolicyDocument)
async def get_document(
    doc_id: str,
    document_service: DocumentService = Depends(get_document_service),
):
    """Get a specific document by ID."""
    try:
        # Validate document ID
        validated_doc_id = validate_document_id(doc_id)
        
        document = await document_service.get_document_by_id(validated_doc_id)
        
        if not document:
            raise HTTPException(
                status_code=404, detail=f"Document not found: {doc_id}"
            )
        
        return document
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get document error: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail="Internal server error while retrieving document"
        )


@router.post("/kb/reindex", response_model=ReindexResponse)
async def reindex_knowledge_base(
    request: ReindexRequest,
    reindex_service: ReindexService = Depends(get_reindex_service),
):
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
        # Validate request
        try:
            request.validate_policy_ids()
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        
        response = await reindex_service.reindex_documents(request)
        return response
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Reindex operation failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail="Internal server error during reindex operation"
        )


@router.delete("/kb/clear")
async def clear_index(
    document_service: DocumentService = Depends(get_document_service),
):
    """
    Clear all documents from the knowledge base.
    
    **WARNING**: This will delete all indexed documents. Use with caution.
    """
    try:
        result = await document_service.clear_all_documents()
        return result
    except Exception as e:
        logger.error(f"Clear index error: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail="Internal server error while clearing index"
        )


@router.get("/kb/status")
async def get_indexing_status(
    reindex_service: ReindexService = Depends(get_reindex_service),
):
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
        logger.error(f"Get indexing status error: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail="Internal server error while getting status"
        )


@router.get("/kb/documents/{document_id}/full", response_model=FullDocumentResponse)
async def get_full_document(document_id: str):
    """Get the full document by combining all its chunks."""
    try:
        # Validate document ID
        validated_doc_id = validate_document_id(document_id)
        
        full_doc = await retrieve_full_document_async(validated_doc_id)
        
        if not full_doc:
            raise HTTPException(
                status_code=404, detail=f"Document not found: {document_id}"
            )
        
        return full_doc
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get full document error: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail="Internal server error while retrieving full document"
        )


@router.get("/kb/documents/{document_id}/chunks", response_model=List[PolicyDocument])
async def get_document_chunks(
    document_id: str,
    document_service: DocumentService = Depends(get_document_service),
):
    """Get all chunks for a specific document."""
    try:
        # Validate document ID
        validated_doc_id = validate_document_id(document_id)
        
        all_documents = await document_service.list_documents(limit=1000)
        chunks = [doc for doc in all_documents if doc.document_id == validated_doc_id]
        
        if not chunks:
            raise HTTPException(status_code=404, detail="Document not found")
        
        return chunks
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get document chunks error: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail="Internal server error while retrieving document chunks"
        )


@router.get("/kb/documents/{document_id}/range", response_model=FullDocumentResponse)
async def get_document_range(
    document_id: str,
    start_chunk: int = Query(0, description="Starting chunk index", ge=0),
    end_chunk: Optional[int] = Query(None, description="Ending chunk index (inclusive)"),
):
    """Get a range of chunks from a document."""
    try:
        # Validate document ID
        validated_doc_id = validate_document_id(document_id)
        
        # Validate chunk range
        if end_chunk is not None and end_chunk < start_chunk:
            raise HTTPException(
                status_code=400,
                detail="End chunk must be greater than or equal to start chunk"
            )
        
        doc_range = get_document_chunk_range(
            validated_doc_id, start_chunk, end_chunk
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
        logger.error(f"Get document range error: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail="Internal server error while retrieving document range"
        )


@router.get("/kb/search")
async def search_documents(
    query: str = Query(..., description="Search query"),
    category: Optional[str] = Query(None, description="Filter by category"),
    max_hits: int = Query(10, description="Maximum number of results", ge=1, le=100),
    search_service: SearchService = Depends(get_search_service),
):
    """
    Search policy documents using keyword search.
    
    - **query**: Search query string
    - **category**: Optional category filter
    - **max_hits**: Maximum number of results to return
    """
    try:
        # Validate inputs
        validated_query = validate_query(query)
        validated_category = validate_category(category) if category else None
        
        # Create search request
        request = SearchRequest(
            query=validated_query,
            category=validated_category,
            max_hits=max_hits,
            search_type="keyword"
        )
        
        result = await search_service.search(request)
        
        return {
            "query": result.query,
            "category": result.category,
            "total_results": result.total_hits,
            "results": [
                {
                    "id": doc.id,
                    "title": doc.title,
                    "content": doc.text,
                    "category": doc.category,
                    "source_file": doc.source_file,
                    "document_id": doc.document_id,
                    "relevance": doc.relevance
                }
                for doc in result.documents
            ]
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Search error: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail="Internal server error during search"
        )


@router.post("/kb/search/vector", response_model=SearchResponse)
async def vector_search(
    request: SearchRequest,
    search_service: SearchService = Depends(get_search_service),
):
    """
    Perform search on policy documents.
    
    Supports three search types:
    - **vector**: Pure semantic search using embeddings
    - **hybrid**: Combines vector and keyword search (recommended)
    - **keyword**: Traditional keyword search
    """
    try:
        # Validate request
        request.query = validate_query(request.query)
        if request.category:
            request.category = validate_category(request.category)
        
        result = await search_service.search(request)
        
        return SearchResponse(
            query=result.query,
            category=result.category,
            total_hits=result.total_hits,
            documents=result.documents,
            search_type=result.search_type
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Search error: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail="Internal server error during search"
        )


# Personal Policy Endpoints
@router.get("/policies", response_model=PolicyListResponse)
async def list_personal_policies(
    category: Optional[str] = Query(None, description="Filter by category (auto, home, life)"),
    limit: int = Query(20, description="Number of policies to return", ge=1, le=100),
    offset: int = Query(0, description="Offset for pagination", ge=0),
):
    """List personal policies with optional filtering."""
    try:
        # Import here to avoid circular imports
        from agents.policies.agent.tools.database.policy_data import get_all_policies
        
        # Get all policies
        all_policies = get_all_policies()
        
        # Filter by category if provided
        if category:
            filtered_policies = [p for p in all_policies if p["policy_category"] == category]
        else:
            filtered_policies = all_policies
        
        # Apply pagination
        paginated_policies = filtered_policies[offset:offset + limit]
        
        # Convert to response models
        policies = [PersonalPolicy(**policy) for policy in paginated_policies]
        
        return PolicyListResponse(
            policies=policies,
            total=len(filtered_policies)
        )
    except Exception as e:
        logger.error(f"List policies error: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail="Internal server error while listing policies"
        )


@router.get("/policies/{policy_number}", response_model=PersonalPolicy)
async def get_personal_policy(policy_number: str):
    """Get a specific personal policy by policy number."""
    try:
        # Import here to avoid circular imports
        from agents.policies.agent.tools.database.policy_data import (
            get_personal_policy_details,
        )
        
        # Get policy details (returns JSON string)
        policy_json = get_personal_policy_details(policy_number)
        
        if policy_json == "Policy not found.":
            raise HTTPException(
                status_code=404, detail=f"Policy not found: {policy_number}"
            )
        
        # Parse the JSON response
        import json
        policy_data = json.loads(policy_json)
        
        return PersonalPolicy(**policy_data)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get policy error: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail="Internal server error while retrieving policy"
        )


@router.post("/kb/upload")
async def upload_document(
    file: UploadFile = File(...),
    category: str = Query("general", description="Document category"),
):
    """
    Upload a document to MinIO for processing.
    
    The document will be:
    1. Uploaded to MinIO inbox folder
    2. Automatically processed by the watcher workflow
    3. Indexed in Vespa if not already present
    
    Supported formats: PDF, DOCX, Markdown, Text
    """
    try:
        # Validate category
        validated_category = validate_category(category)
        
        # Validate file
        if not file.filename:
            raise HTTPException(status_code=400, detail="No filename provided")
            
        # Check file extension
        allowed_extensions = {'.pdf', '.docx', '.md', '.txt'}
        file_ext = Path(file.filename).suffix.lower()
        if file_ext not in allowed_extensions:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type. Allowed: {', '.join(allowed_extensions)}"
            )
            
        # Read file content
        content = await file.read()
        if not content:
            raise HTTPException(status_code=400, detail="Empty file")
            
        # Upload to MinIO
        from agents.policies.ingestion.minio_client import MinIOClient
        
        async with MinIOClient() as minio_client:
            metadata = await minio_client.upload_to_inbox(
                filename=file.filename,
                content=content,
                mime_type=file.content_type or "application/octet-stream"
            )
            
        logger.info(f"Uploaded document {file.filename} with ID {metadata.document_id}")
        
        return {
            "message": "Document uploaded successfully",
            "filename": file.filename,
            "document_id": metadata.document_id,
            "sha256": metadata.sha256,
            "size": metadata.file_size,
            "status": "queued_for_processing"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Upload error: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail="Internal server error during upload"
        )


@router.get("/kb/upload/status")
async def get_upload_status():
    """
    Get the status of the MinIO upload system.
    
    Returns information about:
    - Files in inbox awaiting processing
    - Recently processed files
    - Failed files with errors
    """
    try:
        from agents.policies.ingestion.minio_client import MinIOClient
        
        async with MinIOClient() as minio_client:
            # Get files from different folders
            inbox_files = await minio_client.list_inbox_files()
            
            # Get recent processed files (simplified for now)
            processed_count = 0
            failed_count = 0
            
            # TODO: Implement listing for processed and failed folders
            
        return {
            "inbox_count": len(inbox_files),
            "inbox_files": [
                {
                    "filename": f["filename"],
                    "size": f["size"],
                    "last_modified": f["last_modified"].isoformat() if f["last_modified"] else None,
                    "document_id": f["metadata"].get("document_id")
                }
                for f in inbox_files
            ],
            "processed_count": processed_count,
            "failed_count": failed_count
        }
        
    except Exception as e:
        logger.error(f"Get upload status error: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail="Internal server error while getting upload status"
        )


# Export the router