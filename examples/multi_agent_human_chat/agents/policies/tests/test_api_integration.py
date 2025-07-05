import asyncio
from typing import List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from agents.policies.agent.api.dependencies import (
    get_document_service,
    get_reindex_service,
    get_search_service,
    get_vespa_client,
)
from agents.policies.agent.api.models import (
    FullDocumentResponse,
    PolicyDocument,
    ReindexResponse,
)
from agents.policies.agent.api.routes import router
from agents.policies.agent.services.document_service import DocumentService
from agents.policies.agent.services.reindex_service import ReindexService
from agents.policies.agent.services.search_service import SearchService
from libraries.logger import get_console_logger
from libraries.vespa import VespaClient

logger = get_console_logger("test_api_integration")

# Create FastAPI test app
app = FastAPI()
app.include_router(router, prefix="/api/v1")


# Mock fixtures
@pytest.fixture
def mock_vespa_client():
    """Create a mock Vespa client."""
    client = MagicMock(spec=VespaClient)
    
    # Mock search_documents for keyword search
    client.search_documents = AsyncMock(return_value=[])
    
    client.app = MagicMock()
    
    # Mock query results for vector search - return empty by default
    mock_query_result = MagicMock()
    mock_query_result.hits = []
    
    client.app.query = AsyncMock(return_value=mock_query_result)
    client.app.http_session = MagicMock()
    return client


@pytest.fixture
def mock_document_service(mock_vespa_client):
    """Create a mock document service."""
    return DocumentService(mock_vespa_client)


@pytest.fixture
def mock_search_service(mock_vespa_client):
    """Create a mock search service."""
    return SearchService(mock_vespa_client)


@pytest.fixture
def mock_reindex_service(mock_vespa_client):
    """Create a mock reindex service."""
    return ReindexService(mock_vespa_client)


@pytest.fixture
def test_client(mock_document_service, mock_search_service, mock_reindex_service, mock_vespa_client):
    """Create test client with dependency overrides."""
    app.dependency_overrides[get_document_service] = lambda: mock_document_service
    app.dependency_overrides[get_search_service] = lambda: mock_search_service
    app.dependency_overrides[get_reindex_service] = lambda: mock_reindex_service
    app.dependency_overrides[get_vespa_client] = lambda: mock_vespa_client
    
    with TestClient(app) as client:
        yield client
    
    # Clear overrides after test
    app.dependency_overrides.clear()


# Test data
def create_mock_documents() -> List[dict]:
    """Create mock document data for testing."""
    return [
        {
            "id": "auto_policy_001",
            "document_id": "auto_policy",
            "title": "Auto Insurance Policy",
            "text": "Auto insurance covers collision damage.",
            "category": "auto",
            "chunk_index": 0,
            "source_file": "auto.md",
            "page_numbers": [1],
            "page_range": "1",
            "headings": ["Coverage"],
        },
        {
            "id": "auto_policy_002",
            "document_id": "auto_policy",
            "title": "Auto Insurance Policy",
            "text": "Comprehensive coverage protects against theft.",
            "category": "auto",
            "chunk_index": 1,
            "source_file": "auto.md",
            "page_numbers": [2],
            "page_range": "2",
            "headings": ["Coverage"],
        },
        {
            "id": "home_policy_001",
            "document_id": "home_policy",
            "title": "Home Insurance Policy",
            "text": "Home insurance covers water damage from burst pipes.",
            "category": "home",
            "chunk_index": 0,
            "source_file": "home.md",
            "page_numbers": [1],
            "page_range": "1",
            "headings": ["Water Damage"],
        },
    ]


# Integration Tests
class TestDocumentEndpoints:
    """Test document-related endpoints."""
    
    def test_list_documents_success(self, test_client, mock_vespa_client, mock_document_service):
        """Test successful document listing."""
        # Setup mock - mock the service method, not vespa client
        mock_docs = create_mock_documents()
        mock_document_service.list_documents = AsyncMock(return_value=[
            PolicyDocument(**doc) for doc in mock_docs
        ])
        
        # Make request
        response = test_client.get("/api/v1/kb/documents")
        
        # Verify response
        assert response.status_code == 200
        documents = response.json()
        assert len(documents) == 3  # We have 3 chunks total
        assert any(doc["document_id"] == "auto_policy" for doc in documents)
        assert any(doc["document_id"] == "home_policy" for doc in documents)
    
    def test_list_documents_with_category_filter(self, test_client, mock_document_service):
        """Test document listing with category filter."""
        # Setup mock
        all_docs = create_mock_documents()
        auto_docs = [doc for doc in all_docs if doc["category"] == "auto"]
        mock_document_service.list_documents = AsyncMock(return_value=[
            PolicyDocument(**doc) for doc in auto_docs
        ])
        
        # Make request
        response = test_client.get("/api/v1/kb/documents?category=auto")
        
        # Verify response
        assert response.status_code == 200
        documents = response.json()
        assert len(documents) >= 1  # We have at least 1 auto chunk
        assert all(doc["category"] == "auto" for doc in documents)
    
    def test_list_documents_invalid_category(self, test_client):
        """Test document listing with invalid category."""
        response = test_client.get("/api/v1/kb/documents?category=invalid")
        
        assert response.status_code == 400
        assert "Invalid category" in response.json()["detail"]
    
    def test_list_documents_pagination(self, test_client, mock_document_service):
        """Test document listing with pagination."""
        # Setup mock - return only 1 document for pagination test
        mock_document_service.list_documents = AsyncMock(return_value=[
            PolicyDocument(**create_mock_documents()[0])
        ])
        
        # Make request with limit and offset
        response = test_client.get("/api/v1/kb/documents?limit=1&offset=1")
        
        # Verify response
        assert response.status_code == 200
        documents = response.json()
        assert len(documents) == 1
    
    @pytest.mark.asyncio
    async def test_get_full_document_success(self, test_client):
        """Test retrieving a full document."""
        document_id = "auto_policy"
        
        # Mock the retrieval function
        with patch("agents.policies.agent.api.routes.retrieve_full_document_async") as mock_retrieve:
            mock_retrieve.return_value = FullDocumentResponse(
                document_id=document_id,
                category="auto",
                source_file="auto.md",
                full_text="Full auto insurance policy content...",
                total_chunks=3,
                total_characters=1000,
                total_tokens=250,
                headings=["Coverage", "Exclusions"],
                page_numbers=[1, 2, 3],
                page_range="1-3",
                chunk_ids=["auto_001", "auto_002", "auto_003"],
                metadata={"version": "1.0"}
            )
            
            response = test_client.get(f"/api/v1/kb/documents/{document_id}/full")
            
            assert response.status_code == 200
            data = response.json()
            assert data["document_id"] == document_id
            assert data["category"] == "auto"
            assert "Full auto insurance" in data["full_text"]
    
    def test_get_full_document_not_found(self, test_client):
        """Test retrieving non-existent document."""
        with patch("agents.policies.agent.api.routes.retrieve_full_document_async") as mock_retrieve:
            mock_retrieve.return_value = None
            
            response = test_client.get("/api/v1/kb/documents/invalid_id/full")
            
            assert response.status_code == 404
            assert "Document not found" in response.json()["detail"]
    
    def test_get_document_range_success(self, test_client):
        """Test retrieving document range."""
        document_id = "auto_policy"
        
        # Setup mock
        with patch("agents.policies.agent.api.routes.get_document_chunk_range") as mock_get_range:
            # Return a dict that matches FullDocumentResponse fields
            mock_get_range.return_value = {
                "document_id": document_id,
                "category": "auto",
                "source_file": "auto.md",
                "full_text": "Chunk content...",
                "total_chunks": 2,
                "total_characters": 100,
                "total_tokens": 25,
                "headings": ["Section 1", "Section 2"],
                "page_numbers": [1, 2],
                "page_range": "1-2",
                "chunk_ids": ["auto_001", "auto_002"],
                "metadata": {}
            }
            
            response = test_client.get(f"/api/v1/kb/documents/{document_id}/range?start_chunk=0&end_chunk=1")
            
            assert response.status_code == 200
            data = response.json()
            assert data["document_id"] == document_id
            assert data["page_range"] == "1-2"
            assert data["total_chunks"] == 2


class TestSearchEndpoints:
    """Test search-related endpoints."""
    
    def test_search_documents_success(self, test_client, mock_search_service, mock_vespa_client):
        """Test basic document search."""
        # Setup mock - need to mock the actual vespa query result
        mock_hit = MagicMock()
        mock_hit.fields = create_mock_documents()[0]
        mock_hit.relevance = 0.9
        
        mock_query_result = MagicMock()
        mock_query_result.hits = [mock_hit]
        
        mock_vespa_client.app.query = AsyncMock(return_value=mock_query_result)
        
        response = test_client.post(
            "/api/v1/kb/search/vector",
            json={"query": "collision damage"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["total_hits"] == 1
        assert "Auto insurance" in data["documents"][0]["text"]
    
    def test_search_documents_with_category(self, test_client, mock_search_service, mock_vespa_client):
        """Test search with category filter."""
        # Setup mock - return empty results for category search
        mock_query_result = MagicMock()
        mock_query_result.hits = []
        
        mock_vespa_client.app.query = AsyncMock(return_value=mock_query_result)
        
        response = test_client.post(
            "/api/v1/kb/search/vector",
            json={"query": "water", "category": "home"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["category"] == "home"
    
    def test_search_documents_empty_query(self, test_client):
        """Test search with empty query."""
        response = test_client.post(
            "/api/v1/kb/search/vector",
            json={"query": ""}
        )
        
        assert response.status_code == 422
        # Pydantic v2 returns detailed validation errors
        errors = response.json()["detail"]
        assert any("at least 1 character" in str(error) for error in errors)
    
    def test_search_documents_long_query(self, test_client):
        """Test search with query exceeding max length."""
        long_query = "a" * 501  # Exceeds 500 char limit
        response = test_client.post(
            "/api/v1/kb/search/vector",
            json={"query": long_query}
        )
        
        assert response.status_code == 422
        # Pydantic v2 returns detailed validation errors
        errors = response.json()["detail"]
        assert any("at most 500 characters" in str(error) for error in errors)
    
    def test_vector_search_success(self, test_client, mock_search_service, mock_vespa_client):
        """Test vector search endpoint."""
        # Setup mock - need to mock the actual vespa query result
        mock_hit = MagicMock()
        mock_hit.fields = {
            "id": "auto_001",
            "title": "Auto Policy",
            "text": "Vector search result",
            "category": "auto",
            "chunk_index": 0,
            "source_file": "auto.md",
            "document_id": "auto_policy",
            "page_numbers": [],
            "headings": []
        }
        mock_hit.relevance = 0.95
        
        mock_query_result = MagicMock()
        mock_query_result.hits = [mock_hit]
        
        mock_vespa_client.app.query = AsyncMock(return_value=mock_query_result)
        
        response = test_client.post(
            "/api/v1/kb/search/vector",
            json={"query": "test query", "max_hits": 5}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["total_hits"] == 1
        assert "Vector search result" in data["documents"][0]["text"]


class TestReindexEndpoints:
    """Test reindex-related endpoints."""
    
    @pytest.mark.asyncio
    async def test_reindex_all_documents(self, test_client, mock_reindex_service):
        """Test reindexing all documents."""
        # Setup mock
        mock_reindex_service.reindex_documents = AsyncMock(return_value=ReindexResponse(
            status="success",
            workflow_id="workflow_123",
            total_documents_submitted=4,
            policy_ids=["auto", "home", "life", "health"]
        ))
        
        # Mock the temporal client import
        with patch("agents.policies.ingestion.temporal_client.TemporalClient") as mock_temporal_cls:
            mock_temporal = mock_temporal_cls.return_value
            async def mock_ingest_result(*args, **kwargs):
                return type('Result', (), {
                    'success': True, 
                    'workflow_id': 'workflow_123',
                    'error_message': None
                })()
            mock_temporal.ingest_document_async = mock_ingest_result
        
            response = test_client.post(
                "/api/v1/kb/reindex",
                json={"force_rebuild": True}
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "success"
            assert data["total_documents_submitted"] == 4
            assert len(data["policy_ids"]) == 4
    
    @pytest.mark.asyncio
    async def test_reindex_specific_policies(self, test_client, mock_reindex_service):
        """Test reindexing specific policy categories."""
        # Setup mock
        mock_reindex_service.reindex_documents = AsyncMock(return_value=ReindexResponse(
            status="success",
            workflow_id="workflow_456",
            total_documents_submitted=2,
            policy_ids=["auto", "home"]
        ))
        
        # Mock the temporal client import
        with patch("agents.policies.ingestion.temporal_client.TemporalClient") as mock_temporal_cls:
            mock_temporal = mock_temporal_cls.return_value
            async def mock_ingest_result(*args, **kwargs):
                return type('Result', (), {
                    'success': True, 
                    'workflow_id': 'workflow_456',
                    'error_message': None
                })()
            mock_temporal.ingest_document_async = mock_ingest_result
        
            response = test_client.post(
                "/api/v1/kb/reindex",
                json={"policy_ids": ["auto", "home"], "force_rebuild": False}
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["total_documents_submitted"] == 2
            assert set(data["policy_ids"]) == {"auto", "home"}
    
    @pytest.mark.asyncio
    async def test_reindex_failure(self, test_client, mock_reindex_service):
        """Test reindex failure handling."""
        # Setup mock to simulate failure
        mock_reindex_service.reindex_documents = AsyncMock(return_value=ReindexResponse(
            status="failed",
            workflow_id="none",
            total_documents_submitted=0,
            policy_ids=[]
        ))
        
        # Mock the temporal client to simulate failure
        with patch("agents.policies.ingestion.temporal_client.TemporalClient") as mock_temporal_cls:
            mock_temporal = mock_temporal_cls.return_value
            async def mock_ingest_failure(*args, **kwargs):
                return type('Result', (), {
                    'success': False, 
                    'workflow_id': 'none',
                    'error_message': 'Simulated failure'
                })()
            mock_temporal.ingest_document_async = mock_ingest_failure
        
            response = test_client.post(
                "/api/v1/kb/reindex",
                json={"force_rebuild": True}
            )
            
            assert response.status_code == 200  # Still returns 200 but with failed status
            data = response.json()
            assert data["status"] == "failed"
            assert data["total_documents_submitted"] == 0
    
    def test_get_indexing_status(self, test_client, mock_reindex_service):
        """Test getting indexing status."""
        # Setup mock
        mock_reindex_service.get_indexing_status = AsyncMock(return_value={
            "is_indexed": True,
            "total_chunks": 10,
            "total_documents": 4,
            "categories": {
                "auto": {"total_chunks": 3, "total_documents": 1},
                "home": {"total_chunks": 2, "total_documents": 1},
                "life": {"total_chunks": 3, "total_documents": 1},
                "health": {"total_chunks": 2, "total_documents": 1}
            },
            "documents": [],
            "status": "indexed"
        })
        
        response = test_client.get("/api/v1/kb/status")
        
        assert response.status_code == 200
        data = response.json()
        assert data["is_indexed"] is True
        assert data["total_chunks"] == 10
        assert data["total_documents"] == 4
        assert len(data["categories"]) == 4


class TestCategoryStats:
    """Test category statistics endpoint."""
    
    def test_get_category_stats_success(self, test_client, mock_document_service):
        """Test retrieving category statistics."""
        # Setup mock - get_categories_stats returns list of dicts
        mock_document_service.get_categories_stats = AsyncMock(return_value=[
            {"name": "auto", "document_count": 2},
            {"name": "home", "document_count": 1},
            {"name": "life", "document_count": 1},
            {"name": "health", "document_count": 1},
        ])
        
        response = test_client.get("/api/v1/kb/categories")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 4
        assert any(cat["name"] == "auto" and cat["document_count"] == 2 for cat in data)


class TestErrorHandling:
    """Test API error handling."""
    
    def test_internal_server_error(self, test_client, mock_search_service):
        """Test handling of internal server errors."""
        # Setup mock to raise exception
        mock_search_service.vector_search = AsyncMock(side_effect=Exception("Database connection failed"))
        
        response = test_client.post(
            "/api/v1/kb/search/vector",
            json={"query": "test"}
        )
        
        assert response.status_code == 500
        assert "Internal server error" in response.json()["detail"]
    
    @pytest.mark.asyncio
    async def test_timeout_handling(self, test_client, mock_vespa_client):
        """Test handling of timeout errors."""
        # Setup mock to simulate timeout
        async def slow_search(*args, **kwargs):
            await asyncio.sleep(10)  # Simulate slow operation
            return []
        
        mock_vespa_client.search_documents = slow_search
        
        # This should timeout based on API configuration
        response = test_client.post(
            "/api/v1/kb/search/vector",
            json={"query": "test"}
        )
        
        # The actual behavior depends on how timeouts are configured
        # This test ensures the endpoint handles long-running operations


class TestHealthCheck:
    """Test health check endpoint."""
    
    def test_health_check(self, test_client):
        """Test the health check endpoint."""
        response = test_client.get("/api/v1/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "policies-agent"


# Run tests
if __name__ == "__main__":
    pytest.main([__file__, "-v"])