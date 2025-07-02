from typing import List

from fastapi import APIRouter, HTTPException

from agents.policies.agent.models import (
    FullDocumentResponse,
    PolicyDocument,
    SearchResponse,
    VectorSearchRequest,
)
from agents.policies.agent.routes import vespa_client
from agents.policies.agent.tools.retrieval.full_document_retrieval import (
    retrieve_full_document_async,
)
from agents.policies.embeddings import generate_embedding
from libraries.logger import get_console_logger

router = APIRouter()
logger = get_console_logger("policies_agent")


@router.get("/kb/full-document/{document_id}", response_model=FullDocumentResponse)
async def get_full_document(document_id: str):
    """Retrieve a complete document by reconstructing it from its chunks."""
    try:
        result = await retrieve_full_document_async(document_id, vespa_client)
        if "error" in result:
            raise HTTPException(status_code=404, detail=result["error"])
        return FullDocumentResponse(**result)
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.error("Get full document error: %s", exc)
        raise HTTPException(status_code=500, detail=f"Failed to retrieve full document: {exc}")


@router.post("/kb/search", response_model=SearchResponse)
async def vector_search(request: VectorSearchRequest):
    """Perform semantic or hybrid search across the knowledge base."""
    try:
        valid_search_types = ["vector", "hybrid", "keyword"]
        if request.search_type not in valid_search_types:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid search type. Must be one of: {', '.join(valid_search_types)}",
            )
        query_embedding = generate_embedding(request.query)
        if not query_embedding:
            raise HTTPException(status_code=400, detail="Failed to generate embedding for query")
        if request.search_type == "vector":
            results = await vespa_client.vector_search(
                query_embedding=query_embedding,
                category=request.category,
                max_hits=request.max_hits,
            )
        elif request.search_type == "hybrid":
            results = await vespa_client.hybrid_search(
                query=request.query,
                query_embedding=query_embedding,
                category=request.category,
                max_hits=request.max_hits,
                alpha=request.alpha,
            )
        else:
            results = await vespa_client.search_documents(
                query=request.query,
                category=request.category,
                max_hits=request.max_hits,
            )

        documents: List[PolicyDocument] = []
        for result in results:
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
            )
        return SearchResponse(
            query=request.query,
            category=request.category,
            total_hits=len(results),
            documents=documents,
        )
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.error("Vector search error: %s", exc)
        raise HTTPException(status_code=500, detail=f"Vector search failed: {exc}")
