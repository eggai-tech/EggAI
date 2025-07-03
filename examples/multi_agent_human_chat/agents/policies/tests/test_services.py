"""Unit tests for Policies Agent services.

These tests cover the service layer functionality:
- DocumentService
- SearchService  
- ReindexService
"""

from typing import List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agents.policies.agent.api.models import (
    PolicyDocument,
    ReindexRequest,
    SearchResponse,
    VectorSearchRequest,
)
from agents.policies.agent.services.document_service import DocumentService
from agents.policies.agent.services.reindex_service import ReindexService
from agents.policies.agent.services.search_service import SearchService
from libraries.logger import get_console_logger
from libraries.vespa import VespaClient

logger = get_console_logger("test_services")


# Mock fixtures
@pytest.fixture
def mock_vespa_client():
    """Create a mock Vespa client."""
    client = MagicMock(spec=VespaClient)
    client.search_documents = AsyncMock()
    client.app = MagicMock()
    
    # Mock the app.query method for vector search
    mock_query_result = MagicMock()
    mock_query_result.hits = []
    client.app.query = AsyncMock(return_value=mock_query_result)
    
    # Mock the http_session context manager
    mock_session = AsyncMock()
    mock_session.delete_data_point = AsyncMock(return_value=MagicMock(status_code=200))
    client.app.http_session = MagicMock(return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_session)))
    
    return client


@pytest.fixture
def document_service(mock_vespa_client):
    """Create a DocumentService instance with mock client."""
    return DocumentService(mock_vespa_client)


@pytest.fixture
def search_service(mock_vespa_client):
    """Create a SearchService instance with mock client."""
    return SearchService(mock_vespa_client)


@pytest.fixture
def reindex_service(mock_vespa_client):
    """Create a ReindexService instance with mock client."""
    return ReindexService(mock_vespa_client)


# Test data helpers
def create_mock_documents(category: str = None, count: int = 3) -> List[dict]:
    """Create mock document data."""
    docs = [
        {
            "id": f"{cat}_policy_{i:03d}",
            "document_id": f"{cat}_policy",
            "title": f"{cat.capitalize()} Insurance Policy",
            "text": f"Content for {cat} policy chunk {i}",
            "category": cat,
            "chunk_index": i,
            "source_file": f"{cat}.md",
            "page_numbers": [i + 1],
            "page_range": str(i + 1),
            "headings": [f"Section {i}"],
        }
        for cat in (["auto", "home", "life", "health"] if not category else [category])
        for i in range(count)
    ]
    return docs


class TestDocumentService:
    """Test DocumentService functionality."""
    
    @pytest.mark.asyncio
    async def test_list_documents_all(self, document_service, mock_vespa_client):
        """Test listing all documents."""
        # Setup mock - list_documents uses search_documents internally
        mock_vespa_client.search_documents.return_value = create_mock_documents()
        
        # Execute
        result = await document_service.list_documents()
        
        # Verify
        assert len(result) == 12  # 3 documents per category * 4 categories
        assert all(isinstance(doc, PolicyDocument) for doc in result)
        assert {doc.category for doc in result} == {"auto", "home", "life", "health"}
    
    @pytest.mark.asyncio
    async def test_list_documents_by_category(self, document_service, mock_vespa_client):
        """Test listing documents filtered by category."""
        # Setup mock
        mock_vespa_client.search_documents.return_value = create_mock_documents(category="auto")
        
        # Execute
        result = await document_service.list_documents(category="auto")
        
        # Verify
        assert len(result) == 3  # 3 documents for auto category
        assert all(doc.category == "auto" for doc in result)
        assert all(doc.document_id == "auto_policy" for doc in result)
    
    @pytest.mark.asyncio
    async def test_list_documents_with_pagination(self, document_service, mock_vespa_client):
        """Test document listing with limit and offset."""
        # Setup mock - return enough documents for pagination
        all_docs = create_mock_documents()
        # The list_documents method will apply [offset:offset+limit] to these results
        # With offset=1 and limit=2, it needs at least 3 documents to return 2
        mock_vespa_client.search_documents.return_value = all_docs
        
        # Execute
        result = await document_service.list_documents(limit=2, offset=1)
        
        # Verify
        assert len(result) == 2
        # Should skip first document and return next 2
    
    @pytest.mark.asyncio
    async def test_list_documents_empty_result(self, document_service, mock_vespa_client):
        """Test handling of empty document list."""
        # Setup mock
        mock_vespa_client.search_documents.return_value = []
        
        # Execute
        result = await document_service.list_documents()
        
        # Verify
        assert result == []
    
    
    @pytest.mark.asyncio
    async def test_get_category_stats(self, document_service, mock_vespa_client):
        """Test retrieving category statistics."""
        # Setup mock
        mock_vespa_client.search_documents.return_value = create_mock_documents()
        
        # Execute
        result = await document_service.get_categories_stats()
        
        # Verify
        assert len(result) == 4
        assert all(isinstance(stat, dict) for stat in result)
        assert {stat["name"] for stat in result} == {"auto", "home", "life", "health"}
        assert all(stat["document_count"] == 3 for stat in result)  # 3 chunks per category
    
    @pytest.mark.asyncio
    async def test_list_documents_error_handling(self, document_service, mock_vespa_client):
        """Test error handling in list_documents."""
        # Setup mock to raise exception
        mock_vespa_client.search_documents.side_effect = Exception("Connection failed")
        
        # Execute and verify exception is raised
        with pytest.raises(Exception) as exc_info:
            await document_service.list_documents()
        
        assert "Connection failed" in str(exc_info.value)


class TestSearchService:
    """Test SearchService functionality."""
    
    @pytest.mark.asyncio
    async def test_search_documents_basic(self, search_service, mock_vespa_client):
        """Test basic document search."""
        # Setup mock
        query = "collision damage"
        mock_results = create_mock_documents("auto", 1)
        
        # Mock for hybrid search - create mock hits
        mock_hit = MagicMock()
        mock_hit.fields = mock_results[0]
        mock_hit.relevance = 0.95
        
        mock_query_result = MagicMock()
        mock_query_result.hits = [mock_hit]
        mock_vespa_client.app.query.return_value = mock_query_result
        
        # Execute - use vector_search with a request object
        from agents.policies.agent.api.models import VectorSearchRequest
        request = VectorSearchRequest(query=query, search_type="hybrid")
        
        # Mock embedding generation
        with patch("agents.policies.agent.services.search_service.generate_embedding") as mock_embed:
            mock_embed.return_value = [0.1, 0.2, 0.3]  # Mock embedding vector
            result = await search_service.vector_search(request)
        
        # Verify
        assert isinstance(result, SearchResponse)
        assert result.total_hits == 1
        assert result.query == query
        assert len(result.documents) == 1
        assert "auto" in result.documents[0].text
    
    @pytest.mark.asyncio
    async def test_search_documents_with_category(self, search_service, mock_vespa_client):
        """Test search with category filter."""
        # Setup mock
        query = "water damage"
        category = "home"
        
        # Mock empty results
        mock_query_result = MagicMock()
        mock_query_result.hits = []
        mock_vespa_client.app.query.return_value = mock_query_result
        
        # Execute - use vector_search with a request object
        from agents.policies.agent.api.models import VectorSearchRequest
        request = VectorSearchRequest(query=query, category=category)
        
        # Mock embedding generation
        with patch("agents.policies.agent.services.search_service.generate_embedding") as mock_embed:
            mock_embed.return_value = [0.1, 0.2, 0.3]  # Mock embedding vector
            result = await search_service.vector_search(request)
        
        # Verify
        assert isinstance(result, SearchResponse)
        assert result.category == category
        assert result.total_hits == 0
        # Verify the category filter was applied in the YQL query
        mock_vespa_client.app.query.assert_called_once()
        call_args = mock_vespa_client.app.query.call_args
        assert f"category contains '{category}'" in call_args[1]["yql"]
    
    @pytest.mark.asyncio
    async def test_search_documents_with_limit(self, search_service, mock_vespa_client):
        """Test search with custom limit."""
        # Setup mock
        query = "insurance"
        limit = 5
        mock_docs = create_mock_documents()[:limit]
        
        # Create mock hits
        mock_hits = []
        for doc in mock_docs:
            mock_hit = MagicMock()
            mock_hit.fields = doc
            mock_hit.relevance = 0.9
            mock_hits.append(mock_hit)
        
        mock_query_result = MagicMock()
        mock_query_result.hits = mock_hits
        mock_vespa_client.app.query.return_value = mock_query_result
        
        # Execute - use vector_search with a request object
        from agents.policies.agent.api.models import VectorSearchRequest
        request = VectorSearchRequest(query=query, max_hits=limit)
        
        # Mock embedding generation
        with patch("agents.policies.agent.services.search_service.generate_embedding") as mock_embed:
            mock_embed.return_value = [0.1, 0.2, 0.3]  # Mock embedding vector
            result = await search_service.vector_search(request)
        
        # Verify
        assert isinstance(result, SearchResponse)
        assert len(result.documents) <= limit
        assert result.total_hits == len(mock_hits)
    
    @pytest.mark.asyncio
    async def test_vector_search(self, search_service, mock_vespa_client):
        """Test vector search functionality."""
        # Setup mock
        request = VectorSearchRequest(query="find similar content", max_hits=3)
        mock_results = create_mock_documents("auto", 2)
        
        # Create mock hits
        mock_hits = []
        for doc in mock_results:
            mock_hit = MagicMock()
            mock_hit.fields = doc
            mock_hit.relevance = 0.9
            mock_hits.append(mock_hit)
        
        mock_query_result = MagicMock()
        mock_query_result.hits = mock_hits
        mock_vespa_client.app.query.return_value = mock_query_result
        
        # Mock embedding generation
        with patch("agents.policies.agent.services.search_service.generate_embedding") as mock_embed:
            mock_embed.return_value = [0.1, 0.2, 0.3]  # Mock embedding vector
            
            # Execute
            result = await search_service.vector_search(request)
            
            # Verify
            assert isinstance(result, SearchResponse)
            assert result.total_hits == 2
            assert result.query == request.query
            mock_embed.assert_called_once_with(request.query)
    
    @pytest.mark.asyncio
    async def test_search_error_handling(self, search_service, mock_vespa_client):
        """Test error handling in search."""
        # Setup mock to raise exception
        mock_vespa_client.app.query.side_effect = Exception("Search failed")
        
        # Execute and verify exception is raised
        with patch("agents.policies.agent.services.search_service.generate_embedding") as mock_embed:
            mock_embed.return_value = [0.1, 0.2, 0.3]  # Mock embedding vector
            
            with pytest.raises(Exception) as exc_info:
                from agents.policies.agent.api.models import VectorSearchRequest
                request = VectorSearchRequest(query="test query")
                await search_service.vector_search(request)
            
            assert "Search failed" in str(exc_info.value)


class TestReindexService:
    """Test ReindexService functionality."""
    
    @pytest.mark.asyncio
    async def test_clear_existing_documents(self, reindex_service, mock_vespa_client):
        """Test clearing existing documents."""
        # Setup mock
        existing_docs = create_mock_documents()[:5]
        mock_vespa_client.search_documents.return_value = existing_docs
        
        # Execute
        result = await reindex_service.clear_existing_documents()
        
        # Verify
        assert result == 5  # Should have deleted 5 documents
        # Verify delete was called for each document
        session = mock_vespa_client.app.http_session().__aenter__.return_value
        assert session.delete_data_point.call_count == 5
    
    @pytest.mark.asyncio
    async def test_clear_documents_empty_index(self, reindex_service, mock_vespa_client):
        """Test clearing when no documents exist."""
        # Setup mock
        mock_vespa_client.search_documents.return_value = []
        
        # Execute
        result = await reindex_service.clear_existing_documents()
        
        # Verify
        assert result == 0
    
    @pytest.mark.asyncio
    async def test_get_indexing_status(self, reindex_service, mock_vespa_client):
        """Test retrieving indexing status."""
        # Setup mock
        mock_vespa_client.search_documents.return_value = create_mock_documents()
        
        # Execute
        result = await reindex_service.get_indexing_status()
        
        # Verify
        assert result["is_indexed"] is True
        assert result["total_chunks"] == 12  # 3 chunks * 4 categories
        assert result["total_documents"] == 4
        assert result["status"] == "indexed"
        assert len(result["categories"]) == 4
        assert all(cat in result["categories"] for cat in ["auto", "home", "life", "health"])
    
    def test_get_document_configs_all(self, reindex_service):
        """Test getting all document configurations."""
        # Execute
        configs = reindex_service._get_document_configs()
        
        # Verify
        assert len(configs) == 4
        assert {c["category"] for c in configs} == {"auto", "home", "life", "health"}
        assert all("file" in c and "category" in c for c in configs)
    
    def test_get_document_configs_filtered(self, reindex_service):
        """Test getting filtered document configurations."""
        # Execute
        configs = reindex_service._get_document_configs(["auto", "home"])
        
        # Verify
        assert len(configs) == 2
        assert {c["category"] for c in configs} == {"auto", "home"}
    
    @pytest.mark.asyncio
    async def test_queue_document_for_ingestion_success(self, reindex_service):
        """Test successful document queuing."""
        # Setup mock temporal client
        mock_temporal = AsyncMock()
        mock_temporal.ingest_document_async.return_value = MagicMock(
            success=True,
            workflow_id="workflow_123",
            error_message=None
        )
        
        config = {"file": "auto.md", "category": "auto"}
        
        # Execute
        success, policy_id, error = await reindex_service._queue_document_for_ingestion(
            mock_temporal, config, force_rebuild=True
        )
        
        # Verify
        assert success is True
        assert policy_id == "auto"
        assert error is None
        mock_temporal.ingest_document_async.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_queue_document_file_not_found(self, reindex_service):
        """Test queuing when document file doesn't exist."""
        # Setup
        mock_temporal = AsyncMock()
        config = {"file": "nonexistent.md", "category": "invalid"}
        
        # Execute
        success, policy_id, error = await reindex_service._queue_document_for_ingestion(
            mock_temporal, config, force_rebuild=False
        )
        
        # Verify
        assert success is False
        assert policy_id == "invalid"
        assert "Document not found" in error
    
    def test_create_reindex_response_success(self, reindex_service):
        """Test creating successful reindex response."""
        # Execute
        response = reindex_service._create_reindex_response(
            documents_queued=4,
            queued_policy_ids=["auto", "home", "life", "health"],
            errors=[]
        )
        
        # Verify
        assert response.status == "success"
        assert response.total_documents_submitted == 4
        assert len(response.policy_ids) == 4
    
    def test_create_reindex_response_partial(self, reindex_service):
        """Test creating partial success response."""
        # Execute
        response = reindex_service._create_reindex_response(
            documents_queued=2,
            queued_policy_ids=["auto", "home"],
            errors=["Failed to queue life policy", "Failed to queue health policy"]
        )
        
        # Verify
        assert response.status == "partial"
        assert response.total_documents_submitted == 2
        assert len(response.policy_ids) == 2
    
    def test_create_reindex_response_failed(self, reindex_service):
        """Test creating failed response."""
        # Execute
        response = reindex_service._create_reindex_response(
            documents_queued=0,
            queued_policy_ids=[],
            errors=["All documents failed to queue"]
        )
        
        # Verify
        assert response.status == "failed"
        assert response.total_documents_submitted == 0
        assert len(response.policy_ids) == 0
    
    @pytest.mark.asyncio
    async def test_reindex_documents_full_flow(self, reindex_service, mock_vespa_client):
        """Test full reindex flow with force rebuild."""
        # Setup mocks
        mock_vespa_client.search_documents.return_value = create_mock_documents()[:2]
        
        with patch("agents.policies.ingestion.documentation_temporal_client.DocumentationTemporalClient") as mock_temporal_class:
            mock_temporal = AsyncMock()
            mock_temporal_class.return_value = mock_temporal
            mock_temporal.ingest_document_async.return_value = MagicMock(
                success=True,
                workflow_id="workflow_123",
                error_message=None
            )
            
            # Create request
            request = ReindexRequest(force_rebuild=True, policy_ids=["auto", "home"])
            
            # Execute
            response = await reindex_service.reindex_documents(request)
            
            # Verify
            assert response.status == "success"
            assert response.total_documents_submitted == 2
            assert set(response.policy_ids) == {"auto", "home"}
            
            # Verify clear was called since force_rebuild=True
            assert mock_vespa_client.search_documents.called


# Run tests
if __name__ == "__main__":
    pytest.main([__file__, "-v"])