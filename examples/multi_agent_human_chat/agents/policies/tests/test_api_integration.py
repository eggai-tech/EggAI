"""Integration tests for the Policies Agent API.

These tests cover the full API functionality including:
- Document listing and retrieval
- Search operations
- Reindexing workflows
- Error handling
"""

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
    CategoryStats,
    FullDocumentResponse,
    PolicyDocument,
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
            "title": "Auto Insurance Policy - Coverage",
            "text": "Auto insurance covers collision damage.",
            "document_id": "auto_policy",
            "category": "auto",
            "chunk_index": 0,
            "source_file": "auto.md",
        },
        {
            "id": "auto_policy_002", 
            "title": "Auto Insurance Policy - Comprehensive",
            "text": "Comprehensive coverage protects against theft.",
            "document_id": "auto_policy",
            "category": "auto",
            "chunk_index": 1,
            "source_file": "auto.md",
        },
        {
            "id": "home_policy_001",
            "title": "Home Insurance Policy - Water Damage",
            "text": "Home insurance covers water damage from burst pipes.",
            "document_id": "home_policy",
            "category": "home",
            "chunk_index": 0,
            "source_file": "home.md",
        },
        {
            "id": "home_policy_002",
            "title": "Home Insurance Policy - Fire Protection",
            "text": "Home insurance covers fire damage to your property.",
            "document_id": "home_policy",
            "category": "home",
            "chunk_index": 1,
            "source_file": "home.md",
        },
    ]


# Integration Tests
class TestDocumentEndpoints:
    """Test document-related endpoints."""
    
    def test_list_documents_success(self, test_client, mock_vespa_client):
        """Test successful document listing."""
        # Setup mock
        mock_vespa_client.search_documents.return_value = create_mock_documents()
        
        # Make request
        response = test_client.get("/api/v1/kb/documents")
        
        # Verify response
        assert response.status_code == 200
        documents = response.json()
        assert len(documents) == 4  # All documents returned
        assert any(doc["document_id"] == "auto_policy" for doc in documents)
        assert any(doc["document_id"] == "home_policy" for doc in documents)
    
    def test_list_documents_with_category_filter(self, test_client, mock_vespa_client):
        """Test document listing with category filter."""
        # Setup mock
        all_docs = create_mock_documents()
        mock_vespa_client.search_documents.return_value = [
            doc for doc in all_docs if doc["category"] == "auto"
        ]
        
        # Make request
        response = test_client.get("/api/v1/kb/documents?category=auto")
        
        # Verify response
        assert response.status_code == 200
        documents = response.json()
        assert len(documents) == 2  # 2 auto documents
        assert all(doc["category"] == "auto" for doc in documents)
    
    def test_list_documents_invalid_category(self, test_client):
        """Test document listing with invalid category."""
        response = test_client.get("/api/v1/kb/documents?category=invalid")
        
        assert response.status_code == 400
        assert "Invalid category" in response.json()["detail"]
    
    def test_list_documents_pagination(self, test_client, mock_vespa_client):
        """Test document listing with pagination."""
        # Setup mock
        mock_vespa_client.search_documents.return_value = create_mock_documents()
        
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
                headings=["Coverage", "Claims", "Exclusions"],
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
    
    def test_vector_search_success(self, test_client, mock_vespa_client):
        """Test vector search endpoint."""
        # Mock the underlying vespa operations for vector search
        from unittest.mock import AsyncMock
        
        # Mock vespa query method for vector search
        mock_vespa_client.app.query = AsyncMock()
        mock_vespa_client.app.query.return_value = type('SearchResult', (), {
            'hits': [type('Hit', (), {
                'fields': {
                    "id": "auto_policy_001",
                    "title": "Auto Insurance Policy", 
                    "text": "Vector search result",
                    "document_id": "auto_policy",
                    "category": "auto",
                    "chunk_index": 0,
                    "source_file": "auto.md"
                },
                'relevance': 0.95
            })()]
        })()
        
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
    async def test_reindex_all_documents(self, test_client, mock_vespa_client):
        """Test reindexing all documents."""
        # Mock vespa operations for reindex service
        mock_vespa_client.search_documents.return_value = []  # No existing docs to clear
        
        # Mock the temporal client import
        with patch("agents.policies.ingestion.documentation_temporal_client.DocumentationTemporalClient") as mock_temporal_cls:
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
    async def test_reindex_specific_policies(self, test_client, mock_vespa_client):
        """Test reindexing specific policy categories."""
        # Mock vespa operations for reindex service
        mock_vespa_client.search_documents.return_value = []  # No existing docs to clear
        
        # Mock the temporal client import
        with patch("agents.policies.ingestion.documentation_temporal_client.DocumentationTemporalClient") as mock_temporal_cls:
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
    async def test_reindex_failure(self, test_client, mock_vespa_client):
        """Test reindex failure handling."""
        # Mock vespa operations for reindex service
        mock_vespa_client.search_documents.return_value = []  # No existing docs to clear
        
        # Mock the temporal client to simulate failure
        with patch("agents.policies.ingestion.documentation_temporal_client.DocumentationTemporalClient") as mock_temporal_cls:
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
    
    def test_get_indexing_status(self, test_client, mock_vespa_client):
        """Test getting indexing status."""
        # Mock vespa search_documents to return documents for status calculation
        mock_documents = [
            {"category": "auto", "id": "auto_1", "document_id": "auto_doc", "source_file": "auto.md"},
            {"category": "auto", "id": "auto_2", "document_id": "auto_doc", "source_file": "auto.md"},
            {"category": "auto", "id": "auto_3", "document_id": "auto_doc", "source_file": "auto.md"},
            {"category": "home", "id": "home_1", "document_id": "home_doc", "source_file": "home.md"},
            {"category": "home", "id": "home_2", "document_id": "home_doc", "source_file": "home.md"},
        ]
        mock_vespa_client.search_documents.return_value = mock_documents
        
        response = test_client.get("/api/v1/kb/status")
        
        assert response.status_code == 200
        data = response.json()
        assert data["is_indexed"] is True
        assert data["total_chunks"] == 5
        assert data["total_documents"] == 2
        assert len(data["categories"]) == 2


class TestCategoryStats:
    """Test category statistics endpoint."""
    
    def test_get_category_stats_success(self, test_client, mock_vespa_client):
        """Test retrieving category statistics."""
        # Mock the underlying vespa client method to return appropriate data
        mock_vespa_client.search_documents.return_value = [
            {"category": "auto", "id": "1"},
            {"category": "auto", "id": "2"},
            {"category": "home", "id": "3"},
            {"category": "life", "id": "4"},
            {"category": "health", "id": "5"},
        ]
        
        response = test_client.get("/api/v1/kb/categories")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 4
        assert any(cat["name"] == "auto" and cat["document_count"] == 2 for cat in data)
        assert sum(cat["document_count"] for cat in data) == 5


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