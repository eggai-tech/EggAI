"""Unit tests for Policies Agent tools (database and retrieval)."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agents.policies.agent.tools.database.example_data import (
    EXAMPLE_POLICIES,
    USE_EXAMPLE_DATA,
)
from agents.policies.agent.tools.database.policy_data import get_personal_policy_details
from agents.policies.agent.tools.retrieval.full_document_retrieval import (
    get_document_chunk_range,
    retrieve_full_document_async,
)
from agents.policies.agent.tools.retrieval.policy_search import (
    search_policy_documentation,
)


class TestPolicyDatabase:
    """Test policy database access tool."""
    
    def test_get_personal_policy_details_with_example_data(self):
        """Test retrieving policy details using example data."""
        # Ensure we're using example data
        with patch("agents.policies.agent.tools.database.policy_data.USE_EXAMPLE_DATA", True):
            # Test valid policy number
            result = get_personal_policy_details("A12345")
            assert result != "Policy not found."
            
            # Parse JSON result
            policy_data = json.loads(result)
            assert policy_data["policy_number"] == "A12345"
            assert policy_data["name"] == "John Doe"
            assert policy_data["policy_category"] == "auto"
            assert "premium_amount_usd" in policy_data
            assert "$" in policy_data["premium_amount_usd"]
    
    def test_get_personal_policy_details_not_found(self):
        """Test handling of non-existent policy."""
        with patch("agents.policies.agent.tools.database.policy_data.USE_EXAMPLE_DATA", True):
            result = get_personal_policy_details("INVALID123")
            assert result == "Policy not found."
    
    def test_get_personal_policy_details_empty_input(self):
        """Test handling of empty policy number."""
        result = get_personal_policy_details("")
        assert result == "Policy not found."
        
        result = get_personal_policy_details(None)
        assert result == "Policy not found."
    
    def test_get_personal_policy_details_case_insensitive(self):
        """Test that policy lookup is case-insensitive."""
        with patch("agents.policies.agent.tools.database.policy_data.USE_EXAMPLE_DATA", True):
            # Test lowercase input
            result = get_personal_policy_details("a12345")
            assert result != "Policy not found."
            policy_data = json.loads(result)
            assert policy_data["policy_number"] == "A12345"
    
    def test_get_personal_policy_details_strips_whitespace(self):
        """Test that policy number is stripped of whitespace."""
        with patch("agents.policies.agent.tools.database.policy_data.USE_EXAMPLE_DATA", True):
            result = get_personal_policy_details("  A12345  ")
            assert result != "Policy not found."
            policy_data = json.loads(result)
            assert policy_data["policy_number"] == "A12345"
    
    def test_get_personal_policy_details_formats_premium(self):
        """Test that premium amount is properly formatted."""
        with patch("agents.policies.agent.tools.database.policy_data.USE_EXAMPLE_DATA", True):
            result = get_personal_policy_details("B67890")
            policy_data = json.loads(result)
            
            # Should have both raw and formatted premium
            assert "premium_amount" in policy_data
            assert "premium_amount_usd" in policy_data
            assert policy_data["premium_amount_usd"] == "$300.00"
    
    def test_get_personal_policy_details_production_mode(self):
        """Test behavior when not using example data."""
        with patch("agents.policies.agent.tools.database.policy_data.USE_EXAMPLE_DATA", False):
            # Should return not found since no real database is configured
            result = get_personal_policy_details("A12345")
            assert result == "Policy not found."
    
    def test_get_personal_policy_details_error_handling(self):
        """Test error handling in policy retrieval."""
        with patch("agents.policies.agent.tools.database.policy_data.USE_EXAMPLE_DATA", True):
            with patch("agents.policies.agent.tools.database.policy_data.EXAMPLE_POLICIES", side_effect=Exception("Database error")):
                result = get_personal_policy_details("A12345")
                assert result == "Policy not found."


class TestPolicySearch:
    """Test policy search functionality."""
    
    @pytest.mark.asyncio
    async def test_search_policy_documentation_basic(self):
        """Test basic policy documentation search."""
        with patch("libraries.vespa.VespaClient") as MockVespaClient:
            # Setup mock
            mock_instance = MockVespaClient.return_value
            mock_instance.search_documents = AsyncMock(return_value=[
                {
                    "id": "doc1",
                    "content": "Auto insurance covers collision damage",
                    "category": "auto",
                    "metadata": {"section": "Coverage"}
                }
            ])
            
            # Execute search
            result = await search_policy_documentation("collision damage")
            
            # Verify
            assert "Auto insurance covers collision damage" in result
            assert "#doc1" in result  # Reference should be included
    
    @pytest.mark.asyncio
    async def test_search_policy_documentation_with_category(self):
        """Test search with category filter."""
        with patch("libraries.vespa.VespaClient") as MockVespaClient:
            mock_instance = MockVespaClient.return_value
            mock_instance.search_documents = AsyncMock(return_value=[
                {
                    "id": "home1",
                    "content": "Home insurance covers water damage",
                    "category": "home",
                    "metadata": {"section": "Water Coverage"}
                }
            ])
            
            # Execute search with category
            result = await search_policy_documentation("water damage", category="home")
            
            # Verify category was used in search
            mock_instance.search_documents.assert_called_once()
            call_args = mock_instance.search_documents.call_args
            assert "category:home" in call_args[1]["query"]
    
    @pytest.mark.asyncio
    async def test_search_policy_documentation_no_results(self):
        """Test search with no results."""
        with patch("libraries.vespa.VespaClient") as MockVespaClient:
            mock_instance = MockVespaClient.return_value
            mock_instance.search_documents = AsyncMock(return_value=[])
            
            result = await search_policy_documentation("nonexistent coverage")
            
            assert result == "No relevant documentation found."
    
    @pytest.mark.asyncio
    async def test_search_policy_documentation_multiple_results(self):
        """Test search with multiple results."""
        with patch("libraries.vespa.VespaClient") as MockVespaClient:
            mock_instance = MockVespaClient.return_value
            mock_instance.search_documents = AsyncMock(return_value=[
                {
                    "id": "doc1",
                    "content": "Coverage type 1",
                    "category": "auto",
                    "metadata": {}
                },
                {
                    "id": "doc2",
                    "content": "Coverage type 2",
                    "category": "auto",
                    "metadata": {}
                },
                {
                    "id": "doc3",
                    "content": "Coverage type 3",
                    "category": "auto",
                    "metadata": {}
                }
            ])
            
            result = await search_policy_documentation("coverage")
            
            # Should include all results
            assert "Coverage type 1" in result
            assert "Coverage type 2" in result
            assert "Coverage type 3" in result
            assert "#doc1" in result
            assert "#doc2" in result
            assert "#doc3" in result
    
    @pytest.mark.asyncio
    async def test_search_policy_documentation_error_handling(self):
        """Test error handling in search."""
        with patch("libraries.vespa.VespaClient") as MockVespaClient:
            mock_instance = MockVespaClient.return_value
            mock_instance.search_documents = AsyncMock(side_effect=Exception("Search failed"))
            
            with pytest.raises(Exception) as exc_info:
                await search_policy_documentation("test query")
            
            assert "Search failed" in str(exc_info.value)


class TestFullDocumentRetrieval:
    """Test full document retrieval functionality."""
    
    @pytest.mark.asyncio
    async def test_retrieve_full_document_success(self):
        """Test successful full document retrieval."""
        with patch("libraries.vespa.VespaClient") as MockVespaClient:
            mock_instance = MockVespaClient.return_value
            
            # Mock search results with multiple chunks
            mock_instance.search_documents = AsyncMock(return_value=[
                {
                    "document_id": "auto_policy",
                    "category": "auto",
                    "content": "Chunk 1 content",
                    "chunk_index": 0,
                    "total_chunks": 3,
                    "source_file": "auto.md",
                    "metadata": {"title": "Auto Insurance Policy"}
                },
                {
                    "document_id": "auto_policy",
                    "category": "auto",
                    "content": "Chunk 2 content",
                    "chunk_index": 1,
                    "total_chunks": 3,
                    "source_file": "auto.md",
                    "metadata": {}
                },
                {
                    "document_id": "auto_policy",
                    "category": "auto",
                    "content": "Chunk 3 content",
                    "chunk_index": 2,
                    "total_chunks": 3,
                    "source_file": "auto.md",
                    "metadata": {}
                }
            ])
            
            # Execute
            result = await retrieve_full_document_async("auto_policy")
            
            # Verify
            assert result is not None
            assert result.document_id == "auto_policy"
            assert result.category == "auto"
            assert result.title == "Auto Insurance Policy"
            assert result.content == "Chunk 1 content\n\nChunk 2 content\n\nChunk 3 content"
            assert result.source_file == "auto.md"
    
    @pytest.mark.asyncio
    async def test_retrieve_full_document_not_found(self):
        """Test retrieval of non-existent document."""
        with patch("libraries.vespa.VespaClient") as MockVespaClient:
            mock_instance = MockVespaClient.return_value
            mock_instance.search_documents = AsyncMock(return_value=[])
            
            result = await retrieve_full_document_async("nonexistent_doc")
            
            assert result is None
    
    @pytest.mark.asyncio
    async def test_retrieve_full_document_single_chunk(self):
        """Test retrieval of document with single chunk."""
        with patch("libraries.vespa.VespaClient") as MockVespaClient:
            mock_instance = MockVespaClient.return_value
            mock_instance.search_documents = AsyncMock(return_value=[
                {
                    "document_id": "short_policy",
                    "category": "life",
                    "content": "Single chunk content",
                    "chunk_index": 0,
                    "total_chunks": 1,
                    "source_file": "life.md",
                    "metadata": {}
                }
            ])
            
            result = await retrieve_full_document_async("short_policy")
            
            assert result is not None
            assert result.content == "Single chunk content"
            assert result.title == "Life Insurance Policy"  # Default title
    
    @pytest.mark.asyncio
    async def test_get_document_chunk_range_full_document(self):
        """Test getting full document range."""
        mock_chunks = [
            {"chunk_index": 0, "content": "Chunk 0"},
            {"chunk_index": 1, "content": "Chunk 1"},
            {"chunk_index": 2, "content": "Chunk 2"}
        ]
        
        result = await get_document_chunk_range(mock_chunks, 0, 2)
        
        assert len(result) == 3
        assert result[0]["content"] == "Chunk 0"
        assert result[2]["content"] == "Chunk 2"
    
    @pytest.mark.asyncio
    async def test_get_document_chunk_range_partial(self):
        """Test getting partial chunk range."""
        mock_chunks = [
            {"chunk_index": 0, "content": "Chunk 0"},
            {"chunk_index": 1, "content": "Chunk 1"},
            {"chunk_index": 2, "content": "Chunk 2"},
            {"chunk_index": 3, "content": "Chunk 3"}
        ]
        
        result = await get_document_chunk_range(mock_chunks, 1, 2)
        
        assert len(result) == 2
        assert result[0]["content"] == "Chunk 1"
        assert result[1]["content"] == "Chunk 2"
    
    @pytest.mark.asyncio
    async def test_get_document_chunk_range_out_of_bounds(self):
        """Test chunk range with out of bounds indices."""
        mock_chunks = [
            {"chunk_index": 0, "content": "Chunk 0"},
            {"chunk_index": 1, "content": "Chunk 1"}
        ]
        
        # Request more chunks than available
        result = await get_document_chunk_range(mock_chunks, 0, 5)
        
        assert len(result) == 2  # Should return only available chunks
    
    @pytest.mark.asyncio
    async def test_retrieve_full_document_error_handling(self):
        """Test error handling in document retrieval."""
        with patch("libraries.vespa.VespaClient") as MockVespaClient:
            mock_instance = MockVespaClient.return_value
            mock_instance.search_documents = AsyncMock(side_effect=Exception("Database error"))
            
            with pytest.raises(Exception) as exc_info:
                await retrieve_full_document_async("auto_policy")
            
            assert "Database error" in str(exc_info.value)


class TestExampleData:
    """Test example data module."""
    
    def test_example_policies_structure(self):
        """Test that example policies have correct structure."""
        assert isinstance(EXAMPLE_POLICIES, list)
        assert len(EXAMPLE_POLICIES) > 0
        
        for policy in EXAMPLE_POLICIES:
            assert "policy_number" in policy
            assert "name" in policy
            assert "policy_category" in policy
            assert "premium_amount" in policy
            assert "payment_due_date" in policy
    
    def test_example_policies_categories(self):
        """Test that all categories are represented."""
        categories = {policy["policy_category"] for policy in EXAMPLE_POLICIES}
        expected_categories = {"auto", "home", "life", "health"}
        assert categories == expected_categories
    
    def test_use_example_data_flag(self):
        """Test USE_EXAMPLE_DATA flag exists."""
        assert isinstance(USE_EXAMPLE_DATA, bool)


# Run tests
if __name__ == "__main__":
    pytest.main([__file__, "-v"])