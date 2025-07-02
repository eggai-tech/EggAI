"""Unit tests for Policies Agent validators and utilities."""

import pytest
from fastapi import HTTPException

from agents.policies.agent.api.validators import (
    validate_category,
    validate_document_id,
    validate_policy_number,
    validate_query,
)
from agents.policies.agent.utils.async_helpers import run_async_safe


class TestValidators:
    """Test input validation functions."""
    
    def test_validate_category_valid(self):
        """Test validation of valid categories."""
        assert validate_category("auto") == "auto"
        assert validate_category("home") == "home"
        assert validate_category("life") == "life"
        assert validate_category("health") == "health"
        assert validate_category("AUTO") == "auto"  # Should lowercase
        assert validate_category("Home") == "home"
        assert validate_category(None) is None  # None is valid
    
    def test_validate_category_invalid(self):
        """Test validation of invalid categories."""
        with pytest.raises(HTTPException) as exc_info:
            validate_category("invalid")
        assert exc_info.value.status_code == 400
        assert "Invalid category" in exc_info.value.detail
        
        with pytest.raises(HTTPException):
            validate_category("car")  # Not a valid category
        
        with pytest.raises(HTTPException):
            validate_category("")  # Empty string
    
    def test_validate_query_valid(self):
        """Test validation of valid queries."""
        assert validate_query("collision coverage") == "collision coverage"
        assert validate_query("a") == "a"  # Single character is valid
        assert validate_query("test " * 100) == "test " * 100  # Up to 500 chars
    
    def test_validate_query_invalid(self):
        """Test validation of invalid queries."""
        # Empty query
        with pytest.raises(HTTPException) as exc_info:
            validate_query("")
        assert exc_info.value.status_code == 400
        assert "Query cannot be empty" in exc_info.value.detail
        
        # None query
        with pytest.raises(HTTPException):
            validate_query(None)
        
        # Query too long
        with pytest.raises(HTTPException) as exc_info:
            validate_query("a" * 501)
        assert "Query too long" in exc_info.value.detail
    
    def test_validate_policy_number_valid(self):
        """Test validation of valid policy numbers."""
        assert validate_policy_number("A12345") == "A12345"
        assert validate_policy_number("B67890") == "B67890"
        assert validate_policy_number("Z99999") == "Z99999"
        assert validate_policy_number("a12345") == "A12345"  # Should uppercase
    
    def test_validate_policy_number_invalid(self):
        """Test validation of invalid policy numbers."""
        # Wrong format
        with pytest.raises(HTTPException) as exc_info:
            validate_policy_number("12345A")  # Numbers first
        assert exc_info.value.status_code == 400
        assert "Invalid policy number format" in exc_info.value.detail
        
        # Too short
        with pytest.raises(HTTPException):
            validate_policy_number("A123")
        
        # Too long
        with pytest.raises(HTTPException):
            validate_policy_number("A1234567")
        
        # No letter
        with pytest.raises(HTTPException):
            validate_policy_number("123456")
        
        # Multiple letters
        with pytest.raises(HTTPException):
            validate_policy_number("AB1234")
        
        # Special characters
        with pytest.raises(HTTPException):
            validate_policy_number("A-12345")
    
    def test_validate_document_id_valid(self):
        """Test validation of valid document IDs."""
        assert validate_document_id("auto_policy") == "auto_policy"
        assert validate_document_id("home_insurance_2023") == "home_insurance_2023"
        assert validate_document_id("policy-123") == "policy-123"
        assert validate_document_id("a" * 100) == "a" * 100  # Long but valid
    
    def test_validate_document_id_invalid(self):
        """Test validation of invalid document IDs."""
        # Empty ID
        with pytest.raises(HTTPException) as exc_info:
            validate_document_id("")
        assert exc_info.value.status_code == 400
        assert "Document ID cannot be empty" in exc_info.value.detail
        
        # None ID
        with pytest.raises(HTTPException):
            validate_document_id(None)
        
        # Invalid characters
        with pytest.raises(HTTPException) as exc_info:
            validate_document_id("policy@123")
        assert "Invalid characters" in exc_info.value.detail
        
        with pytest.raises(HTTPException):
            validate_document_id("policy#123")
        
        with pytest.raises(HTTPException):
            validate_document_id("policy!123")
        
        # ID too long
        with pytest.raises(HTTPException) as exc_info:
            validate_document_id("a" * 201)
        assert "Document ID too long" in exc_info.value.detail


class TestAsyncHelpers:
    """Test async utility functions."""
    
    def test_run_async_safe_without_event_loop(self):
        """Test run_async_safe when no event loop is running."""
        async def async_function():
            return "test_result"
        
        result = run_async_safe(async_function())
        assert result == "test_result"
    
    def test_run_async_safe_with_event_loop(self):
        """Test run_async_safe when an event loop is already running."""
        import asyncio
        
        async def test_function():
            # This simulates being called from within an async context
            async def inner_async():
                return "nested_result"
            
            # This would normally fail if called directly with asyncio.run()
            result = run_async_safe(inner_async())
            return result
        
        # Run the test in an event loop
        result = asyncio.run(test_function())
        assert result == "nested_result"
    
    def test_run_async_safe_with_exception(self):
        """Test run_async_safe propagates exceptions correctly."""
        async def failing_function():
            raise ValueError("Test exception")
        
        with pytest.raises(ValueError) as exc_info:
            run_async_safe(failing_function())
        
        assert "Test exception" in str(exc_info.value)
    
    def test_run_async_safe_with_parameters(self):
        """Test run_async_safe with coroutine that returns complex data."""
        async def complex_function(x: int, y: int) -> dict:
            await asyncio.sleep(0.001)  # Simulate some async work
            return {"sum": x + y, "product": x * y}
        
        result = run_async_safe(complex_function(3, 4))
        assert result == {"sum": 7, "product": 12}


class TestConstants:
    """Test that constants are properly defined."""
    
    def test_valid_categories_constant(self):
        """Test VALID_CATEGORIES is properly defined."""
        from agents.policies.agent.api.validators import VALID_CATEGORIES
        
        assert isinstance(VALID_CATEGORIES, set)
        assert VALID_CATEGORIES == {"auto", "home", "life", "health"}
        assert len(VALID_CATEGORIES) == 4
    
    def test_max_query_length_constant(self):
        """Test MAX_QUERY_LENGTH is properly defined."""
        from agents.policies.agent.api.validators import MAX_QUERY_LENGTH
        
        assert isinstance(MAX_QUERY_LENGTH, int)
        assert MAX_QUERY_LENGTH == 500
    
    def test_max_document_id_length_constant(self):
        """Test MAX_DOCUMENT_ID_LENGTH is properly defined."""
        from agents.policies.agent.api.validators import MAX_DOCUMENT_ID_LENGTH
        
        assert isinstance(MAX_DOCUMENT_ID_LENGTH, int)
        assert MAX_DOCUMENT_ID_LENGTH == 200


# Run tests
if __name__ == "__main__":
    pytest.main([__file__, "-v"])