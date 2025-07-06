"""Tests for Frontend main endpoints"""
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

# Mock the kafka transport before importing the app
with patch('agents.frontend.main.create_kafka_transport'):
    with patch('agents.frontend.main.eggai_set_default_transport'):
        from agents.frontend.main import api


@pytest.fixture
def client():
    """Create a test client"""
    return TestClient(api)


@pytest.fixture
def mock_html_content():
    """Mock HTML content"""
    return "<html><body>Test Content</body></html>"


@patch('agents.frontend.main.aiofiles.open')
@patch('agents.frontend.main.Path.is_file')
def test_read_root_success(mock_is_file, mock_aiofiles_open, client, mock_html_content):
    """Test successful reading of index.html"""
    # Setup mocks
    mock_is_file.return_value = True
    
    # Create async mock for file operations
    async_mock = AsyncMock()
    async_mock.__aenter__.return_value.read = AsyncMock(return_value=mock_html_content)
    mock_aiofiles_open.return_value = async_mock
    
    # Make request
    response = client.get("/")
    
    # Assertions
    assert response.status_code == 200
    assert response.headers["content-type"] == "text/html; charset=utf-8"


@patch('agents.frontend.main.Path.is_file')
def test_read_root_file_not_found(mock_is_file, client):
    """Test when index.html is not found"""
    # Setup mock
    mock_is_file.return_value = False
    
    # Make request
    response = client.get("/")
    
    # Assertions
    assert response.status_code == 404
    assert "File not found" in response.json()["detail"]


@patch('agents.frontend.main.aiofiles.open')
@patch('agents.frontend.main.Path.is_file')
def test_read_admin_success(mock_is_file, mock_aiofiles_open, client, mock_html_content):
    """Test successful reading of admin.html"""
    # Setup mocks
    mock_is_file.return_value = True
    
    # Create async mock for file operations
    async_mock = AsyncMock()
    async_mock.__aenter__.return_value.read = AsyncMock(return_value=mock_html_content)
    mock_aiofiles_open.return_value = async_mock
    
    # Make request
    response = client.get("/admin.html")
    
    # Assertions
    assert response.status_code == 200
    assert response.headers["content-type"] == "text/html; charset=utf-8"


@patch('agents.frontend.main.Path.is_file')
def test_read_admin_file_not_found(mock_is_file, client):
    """Test when admin.html is not found"""
    # Setup mock
    mock_is_file.return_value = False
    
    # Make request
    response = client.get("/admin.html")
    
    # Assertions
    assert response.status_code == 404
    assert "File not found" in response.json()["detail"]


@patch('agents.frontend.main.aiofiles.open')
@patch('agents.frontend.main.Path.is_file')
def test_read_root_generic_error(mock_is_file, mock_aiofiles_open, client):
    """Test generic error handling"""
    # Setup mocks
    mock_is_file.return_value = True
    mock_aiofiles_open.side_effect = Exception("Test error")
    
    # Make request
    response = client.get("/")
    
    # Assertions
    assert response.status_code == 500
    assert "An error occurred" in response.json()["detail"]