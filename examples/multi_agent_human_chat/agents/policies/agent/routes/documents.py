from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query

from agents.policies.agent.models import PolicyDocument
from agents.policies.agent.routes import vespa_client
from agents.policies.agent.tools.retrieval.full_document_retrieval import (
    get_document_chunk_range,
)
from libraries.logger import get_console_logger

router = APIRouter()
logger = get_console_logger("policies_agent")


@router.get("/kb/documents", response_model=List[PolicyDocument])
async def list_documents(
    category: Optional[str] = Query(None, description="Filter by category"),
    limit: int = Query(20, description="Number of documents to return", ge=1, le=100),
    offset: int = Query(0, description="Offset for pagination", ge=0),
):
    """List all documents in the knowledge base."""
    try:
        query = ""
        results = await vespa_client.search_documents(
            query=query,
            category=category,
            max_hits=limit + offset,
        )
        paginated_results = results[offset : offset + limit]
        documents = []
        for result in paginated_results:
            citation = None
            if result.get("page_range"):
                citation = f"{result.get('source_file', 'Unknown')}, page {result['page_range']}"
            documents.append(
                PolicyDocument(
                    id=result.get("id", ""),
                    title=result.get("title", ""),
                    text=result.get("text", ""),
                    category=result.get("category", ""),
                    chunk_index=result.get("chunk_index", 0),
                    source_file=result.get("source_file", ""),
                    page_numbers=result.get("page_numbers", []),
                    page_range=result.get("page_range"),
                    headings=result.get("headings", []),
                    citation=citation,
                    document_id=result.get("document_id"),
                    previous_chunk_id=result.get("previous_chunk_id"),
                    next_chunk_id=result.get("next_chunk_id"),
                    chunk_position=result.get("chunk_position"),
                )
            )
        return documents
    except Exception as exc:  # noqa: BLE001
        logger.error("List documents error: %s", exc)
        raise HTTPException(status_code=500, detail=f"Failed to list documents: {exc}")


@router.get("/kb/document/{doc_id}")
async def get_document(doc_id: str):
    """Retrieve a specific document by ID."""
    try:
        results = await vespa_client.search_documents(query=f'id:"{doc_id}"', max_hits=1)
        if not results:
            raise HTTPException(status_code=404, detail="Document not found")
        result = results[0]
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
            page_numbers=result.get("page_numbers", []),
            page_range=result.get("page_range"),
            headings=result.get("headings", []),
            citation=citation,
            document_id=result.get("document_id"),
            previous_chunk_id=result.get("previous_chunk_id"),
            next_chunk_id=result.get("next_chunk_id"),
            chunk_position=result.get("chunk_position"),
        )
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.error("Get document error: %s", exc)
        raise HTTPException(status_code=500, detail=f"Failed to get document: {exc}")


@router.get("/kb/document-range/{document_id}")
async def get_document_range(
    document_id: str,
    start_chunk: int = Query(..., description="Starting chunk index (0-based)"),
    end_chunk: Optional[int] = Query(None, description="Ending chunk index (inclusive)"),
):
    """Retrieve a specific range of chunks from a document."""
    try:
        result = get_document_chunk_range(document_id, start_chunk, end_chunk, vespa_client)
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        return result
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.error("Get document range error: %s", exc)
        raise HTTPException(status_code=500, detail=f"Failed to retrieve document range: {exc}")
