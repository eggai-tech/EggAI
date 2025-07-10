from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from sentence_transformers import SentenceTransformer

from agents.policies.agent.services.embeddings import generate_embedding
from libraries.integrations.vespa import VespaClient
from libraries.observability.logger import get_console_logger

if TYPE_CHECKING:
    from agents.policies.agent.api.models import (
        PolicyDocument,
        SearchResponse,
        VectorSearchRequest,
    )

logger = get_console_logger("search_service")


class SearchService:
    """Service for searching policy documents."""

    def __init__(self, vespa_client: VespaClient, embedding_model: Optional[SentenceTransformer] = None):
        self.vespa_client = vespa_client
        self._embedding_model = embedding_model

    def create_policy_document(self, doc_data: dict) -> PolicyDocument:
        """Convert raw document data to PolicyDocument model.
        
        Args:
            doc_data: Raw document data from Vespa
            
        Returns:
            PolicyDocument instance
        """
        from agents.policies.agent.api.models import PolicyDocument
        
        # Generate citation
        citation = None
        if doc_data.get("page_range"):
            citation = f"{doc_data.get('source_file', 'Unknown')}, page {doc_data['page_range']}"

        return PolicyDocument(
            id=doc_data.get("id", ""),
            title=doc_data.get("title", ""),
            text=doc_data.get("text", ""),
            category=doc_data.get("category", ""),
            chunk_index=doc_data.get("chunk_index", 0),
            source_file=doc_data.get("source_file", ""),
            relevance=doc_data.get("relevance"),
            # Enhanced metadata
            page_numbers=doc_data.get("page_numbers", []),
            page_range=doc_data.get("page_range"),
            headings=doc_data.get("headings", []),
            citation=citation,
            # Relationships
            document_id=doc_data.get("document_id"),
            previous_chunk_id=doc_data.get("previous_chunk_id"),
            next_chunk_id=doc_data.get("next_chunk_id"),
            chunk_position=doc_data.get("chunk_position"),
        )

    async def vector_search(self, request: VectorSearchRequest) -> SearchResponse:
        """Perform vector-based semantic search.
        
        Args:
            request: Vector search request parameters
            
        Returns:
            SearchResponse object
        """
        from agents.policies.agent.api.models import SearchResponse
        
        try:
            results = []

            if request.search_type in ["vector", "hybrid"]:
                # Generate embedding for the query
                query_embedding = generate_embedding(request.query)

                # Build YQL query based on search type
                if request.search_type == "vector":
                    # Pure vector search
                    yql = f"select * from policy_document where {{targetHits:{request.max_hits}}}nearestNeighbor(embedding,query_embedding)"
                else:
                    # Hybrid search (combine vector and keyword)
                    text_match = "userQuery() or "
                    yql = f"select * from policy_document where ({text_match}({{targetHits:{request.max_hits}}}nearestNeighbor(embedding,query_embedding))) limit {request.max_hits}"

                # Add category filter if specified
                if request.category:
                    yql = yql.replace(
                        "from policy_document where",
                        f"from policy_document where category contains '{request.category}' and",
                    )

                # Execute search based on search type
                if request.search_type == "vector":
                    # Use VespaClient's vector_search method
                    results = await self.vespa_client.vector_search(
                        query_embedding=query_embedding,
                        category=request.category,
                        max_hits=request.max_hits,
                        ranking_profile="semantic"
                    )
                else:
                    # Use VespaClient's hybrid_search method
                    results = await self.vespa_client.hybrid_search(
                        query=request.query,
                        query_embedding=query_embedding,
                        category=request.category,
                        max_hits=request.max_hits,
                        alpha=0.7  # 70% semantic, 30% keyword
                    )

            else:
                # Keyword search
                results = await self.vespa_client.search_documents(
                    query=request.query,
                    category=request.category,
                    max_hits=request.max_hits,
                )

            # Convert to PolicyDocument models
            documents = [self.create_policy_document(result) for result in results]

            return SearchResponse(
                query=request.query,
                category=request.category,
                total_hits=len(documents),
                documents=documents
            )

        except Exception as e:
            logger.error(f"Vector search error: {e}")
            raise