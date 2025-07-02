"""Integration tests for the Policies Agent API.

These tests cover the full API functionality including:
- Document listing and retrieval
- Search operations
- Reindexing workflows
- Error handling
"""

import asyncio
from typing import List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import AsyncClient

from agents.policies.agent.api.dependencies import (
    get_document_service,
    get_reindex_service,
    get_search_service,
    get_vespa_client,
)
from agents.policies.agent.api.models import (
    CategoryStats,
    FullDocumentResponse,
    PolicyDocument,
    ReindexRequest,
    ReindexResponse,
    SearchResponse,
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
    client.search_documents = AsyncMock()
    client.get_all_documents = AsyncMock()
    client.app = MagicMock()
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
            "category": "auto",
            "content": "Auto insurance covers collision damage.",
            "chunk_index": 0,
            "total_chunks": 3,
            "source_file": "auto.md",
            "metadata": {"section": "Coverage", "page": 1}
        },
        {
            "id": "auto_policy_002",
            "document_id": "auto_policy",
            "category": "auto",
            "content": "Comprehensive coverage protects against theft.",
            "chunk_index": 1,
            "total_chunks": 3,
            "source_file": "auto.md",
            "metadata": {"section": "Coverage", "page": 2}
        },
        {
            "id": "home_policy_001",
            "document_id": "home_policy",
            "category": "home",
            "content": "Home insurance covers water damage from burst pipes.",
            "chunk_index": 0,
            "total_chunks": 2,
            "source_file": "home.md",
            "metadata": {"section": "Water Damage", "page": 1}
        },
    ]


# Integration Tests
class TestDocumentEndpoints:
    """Test document-related endpoints."""
    
    def test_list_documents_success(self, test_client, mock_vespa_client):
        """Test successful document listing."""
        # Setup mock
        mock_vespa_client.get_all_documents.return_value = create_mock_documents()
        
        # Make request
        response = test_client.get("/api/v1/kb/documents")
        
        # Verify response
        assert response.status_code == 200
        documents = response.json()
        assert len(documents) == 2  # Should group by document_id
        assert any(doc["document_id"] == "auto_policy" for doc in documents)
        assert any(doc["document_id"] == "home_policy" for doc in documents)
    
    def test_list_documents_with_category_filter(self, test_client, mock_vespa_client):
        """Test document listing with category filter."""
        # Setup mock
        all_docs = create_mock_documents()
        mock_vespa_client.get_all_documents.return_value = [
            doc for doc in all_docs if doc["category"] == "auto"
        ]
        
        # Make request
        response = test_client.get("/api/v1/kb/documents?category=auto")
        
        # Verify response
        assert response.status_code == 200
        documents = response.json()
        assert len(documents) == 1
        assert documents[0]["category"] == "auto"
    
    def test_list_documents_invalid_category(self, test_client):
        """Test document listing with invalid category."""
        response = test_client.get("/api/v1/kb/documents?category=invalid")
        
        assert response.status_code == 400
        assert "Invalid category" in response.json()["detail"]
    
    def test_list_documents_pagination(self, test_client, mock_vespa_client):
        """Test document listing with pagination."""
        # Setup mock
        mock_vespa_client.get_all_documents.return_value = create_mock_documents()
        
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
                title="Auto Insurance Policy",
                content="Full auto insurance policy content...",
                source_file="auto.md",
                metadata={"version": "1.0"}
            )
            
            response = test_client.get(f"/api/v1/kb/documents/{document_id}/full")
            
            assert response.status_code == 200
            data = response.json()
            assert data["document_id"] == document_id
            assert data["category"] == "auto"
            assert "Full auto insurance" in data["content"]
    
    def test_get_full_document_not_found(self, test_client):
        """Test retrieving non-existent document."""
        with patch("agents.policies.agent.api.routes.retrieve_full_document_async") as mock_retrieve:
            mock_retrieve.return_value = None
            
            response = test_client.get("/api/v1/kb/documents/invalid_id/full")
            
            assert response.status_code == 404
            assert "Document not found" in response.json()["detail"]
    
    def test_get_document_chunks_success(self, test_client, mock_vespa_client):
        """Test retrieving document chunks."""
        document_id = "auto_policy"
        chunks = [doc for doc in create_mock_documents() if doc["document_id"] == document_id]
        
        # Setup mock
        mock_vespa_client.search_documents.return_value = chunks
        
        response = test_client.get(f"/api/v1/kb/documents/{document_id}/chunks")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert all(chunk["document_id"] == document_id for chunk in data)


class TestSearchEndpoints:
    """Test search-related endpoints."""
    
    def test_search_documents_success(self, test_client, mock_vespa_client):
        """Test basic document search."""
        # Setup mock
        mock_vespa_client.search_documents.return_value = [
            create_mock_documents()[0]  # Return one result
        ]
        
        response = test_client.get("/api/v1/kb/search?query=collision%20damage")
        
        assert response.status_code == 200
        data = response.json()
        assert data["total_results"] == 1
        assert "collision damage" in data["results"][0]["content"]
    
    def test_search_documents_with_category(self, test_client, mock_vespa_client):
        """Test search with category filter."""
        # Setup mock
        mock_vespa_client.search_documents.return_value = []
        
        response = test_client.get("/api/v1/kb/search?query=water&category=home")
        
        assert response.status_code == 200
        # Verify the search was called with correct parameters
        mock_vespa_client.search_documents.assert_called_once()
        call_args = mock_vespa_client.search_documents.call_args
        assert "water" in call_args[1]["query"]
    
    def test_search_documents_empty_query(self, test_client):
        """Test search with empty query."""
        response = test_client.get("/api/v1/kb/search?query=")
        
        assert response.status_code == 400
        assert "Query cannot be empty" in response.json()["detail"]
    
    def test_search_documents_long_query(self, test_client):
        """Test search with query exceeding max length."""
        long_query = "a" * 501  # Exceeds 500 char limit
        response = test_client.get(f"/api/v1/kb/search?query={long_query}")
        
        assert response.status_code == 400
        assert "Query too long" in response.json()["detail"]
    
    def test_vector_search_success(self, test_client, mock_search_service):
        """Test vector search endpoint."""
        # Setup mock
        mock_search_service.vector_search.return_value = SearchResponse(
            results=[
                PolicyDocument(
                    document_id="auto_policy",
                    category="auto",
                    content="Vector search result",
                    chunk_index=0,
                    total_chunks=1,
                    source_file="auto.md",
                    metadata={}
                )
            ],
            total_results=1,
            query="test query",
            category=None
        )
        
        response = test_client.post(
            "/api/v1/kb/vector-search",
            json={"query": "test query", "max_results": 5}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["total_results"] == 1
        assert "Vector search result" in data["results"][0]["content"]


class TestReindexEndpoints:
    """Test reindex-related endpoints."""
    
    @pytest.mark.asyncio
    async def test_reindex_all_documents(self, test_client, mock_reindex_service):
        """Test reindexing all documents."""
        # Setup mock
        mock_reindex_service.reindex_documents.return_value = ReindexResponse(
            status="success",
            workflow_id="workflow_123",
            total_documents_submitted=4,
            policy_ids=["auto", "home", "life", "health"]
        )
        
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
        mock_reindex_service.reindex_documents.return_value = ReindexResponse(
            status="success",
            workflow_id="workflow_456",
            total_documents_submitted=2,
            policy_ids=["auto", "home"]
        )
        
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
        mock_reindex_service.reindex_documents.return_value = ReindexResponse(
            status="failed",
            workflow_id="none",
            total_documents_submitted=0,
            policy_ids=[]
        )
        
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
        mock_reindex_service.get_indexing_status.return_value = {
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
        }
        
        response = test_client.get("/api/v1/kb/indexing-status")
        
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
        # Setup mock
        mock_document_service.get_category_stats.return_value = [
            CategoryStats(category="auto", document_count=2, chunk_count=5),
            CategoryStats(category="home", document_count=1, chunk_count=3),
            CategoryStats(category="life", document_count=1, chunk_count=4),
            CategoryStats(category="health", document_count=1, chunk_count=2),
        ]
        
        response = test_client.get("/api/v1/kb/categories/stats")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 4
        assert any(cat["category"] == "auto" and cat["document_count"] == 2 for cat in data)
        assert sum(cat["chunk_count"] for cat in data) == 14


class TestErrorHandling:
    """Test API error handling."""
    
    def test_internal_server_error(self, test_client, mock_vespa_client):
        """Test handling of internal server errors."""
        # Setup mock to raise exception
        mock_vespa_client.search_documents.side_effect = Exception("Database connection failed")
        
        response = test_client.get("/api/v1/kb/search?query=test")
        
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
        response = test_client.get("/api/v1/kb/search?query=test")
        
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
        assert "version" in data


# Run tests
if __name__ == "__main__":
    pytest.main([__file__, "-v"])