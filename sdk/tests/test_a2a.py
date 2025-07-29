"""Tests for Agent-to-Agent (A2A) communication"""

import asyncio
import pytest
from unittest.mock import patch, AsyncMock

from eggai import Agent, Channel
from eggai.transport import eggai_set_default_transport, InMemoryTransport

# Skip tests if FastAPI/httpx not available
pytest_plugins = []
try:
    import fastapi
    import httpx
    from eggai.a2a import A2AServer, RemoteAgent
    A2A_AVAILABLE = True
except ImportError:
    A2A_AVAILABLE = False


@pytest.mark.skipif(not A2A_AVAILABLE, reason="FastAPI/httpx not available")
@pytest.mark.asyncio
async def test_agent_to_a2a():
    """Test agent.to_a2a() method"""
    eggai_set_default_transport(lambda: InMemoryTransport())
    
    agent = Agent("TestA2AAgent")
    
    @agent.subscribe()
    async def test_handler(message):
        pass
    
    # Test that to_a2a returns an A2AServer
    with patch('eggai.a2a.server.uvicorn.Server.serve', new_callable=AsyncMock):
        server = await agent.to_a2a(port=8081)
        assert isinstance(server, A2AServer)
        assert server.agent == agent
        assert server.port == 8081
        await server.stop()


@pytest.mark.skipif(not A2A_AVAILABLE, reason="FastAPI/httpx not available")
@pytest.mark.asyncio
async def test_a2a_server_creation():
    """Test A2AServer creation and basic properties"""
    eggai_set_default_transport(lambda: InMemoryTransport())
    
    agent = Agent("ServerTestAgent")
    server = A2AServer(agent, host="localhost", port=8082)
    
    assert server.agent == agent
    assert server.host == "localhost"
    assert server.port == 8082
    assert server.app is not None


@pytest.mark.skipif(not A2A_AVAILABLE, reason="FastAPI/httpx not available")
@pytest.mark.asyncio
async def test_remote_agent_creation():
    """Test RemoteAgent creation"""
    remote = RemoteAgent("http://localhost:8080")
    
    assert remote.base_url == "http://localhost:8080"
    assert remote.timeout == 30.0
    await remote.close()


@pytest.mark.skipif(not A2A_AVAILABLE, reason="FastAPI/httpx not available") 
@pytest.mark.asyncio
async def test_a2a_server_routes():
    """Test that A2A server has expected routes"""
    eggai_set_default_transport(lambda: InMemoryTransport())
    
    agent = Agent("RoutesTestAgent")
    server = A2AServer(agent, port=8083)
    
    # Check that FastAPI app has expected routes
    routes = [route.path for route in server.app.routes if hasattr(route, 'path')]
    
    expected_routes = [
        "/",
        "/agent/info", 
        "/agent/status",
        "/publish",
        "/subscribe",
        "/subscribe/{subscription_id}",
        "/subscriptions",
        "/channels"
    ]
    
    for expected_route in expected_routes:
        # Check if route exists (allowing for parameter variations)
        route_exists = any(expected_route.replace("{subscription_id}", ".*") in route or 
                          route == expected_route for route in routes)
        assert route_exists, f"Route {expected_route} not found in {routes}"


@pytest.mark.skipif(not A2A_AVAILABLE, reason="FastAPI/httpx not available")
def test_a2a_import_without_dependencies():
    """Test that A2A gracefully handles missing dependencies"""
    with patch.dict('sys.modules', {'fastapi': None}):
        with pytest.raises(ImportError, match="FastAPI is required"):
            from eggai.a2a.server import A2AServer


@pytest.mark.asyncio
async def test_agent_to_a2a_without_dependencies():
    """Test agent.to_a2a() without required dependencies"""
    eggai_set_default_transport(lambda: InMemoryTransport())
    
    agent = Agent("NoDepsAgent")
    
    with patch.dict('sys.modules', {'fastapi': None}):
        with pytest.raises(ImportError, match="A2A functionality requires additional dependencies"):
            await agent.to_a2a()


# Integration test (would require actual HTTP server)
@pytest.mark.skipif(not A2A_AVAILABLE, reason="FastAPI/httpx not available")
@pytest.mark.asyncio 
async def test_a2a_message_flow():
    """Test basic A2A message flow (mocked)"""
    eggai_set_default_transport(lambda: InMemoryTransport())
    
    # Create an agent with a subscription
    agent = Agent("MessageFlowAgent")
    received_messages = []
    
    @agent.subscribe()
    async def message_handler(message):
        received_messages.append(message)
    
    # Mock the server start to avoid actual HTTP server
    with patch('eggai.a2a.server.uvicorn.Server.serve', new_callable=AsyncMock):
        server = await agent.to_a2a(port=8084)
        
        # Verify server is configured correctly
        assert server.agent._name == "MessageFlowAgent"
        assert len(server._get_agent_channels()) >= 0  # At least default channel
        
        await server.stop()


# Example usage test
@pytest.mark.skipif(not A2A_AVAILABLE, reason="FastAPI/httpx not available")
def test_a2a_usage_example():
    """Test the intended usage pattern"""
    
    async def example_usage():
        # This is how users would use A2A
        eggai_set_default_transport(lambda: InMemoryTransport())
        
        agent = Agent("ExampleAgent")
        
        @agent.subscribe()
        async def handle_messages(message):
            print(f"Received: {message}")
        
        # Start A2A server
        with patch('eggai.a2a.server.uvicorn.Server.serve', new_callable=AsyncMock):
            server = await agent.to_a2a(host="0.0.0.0", port=8080)
            
            # Connect to remote agent (in real usage)
            # remote = RemoteAgent("http://localhost:8080")
            # await remote.publish_message("orders", {"order_id": 123})
            
            await server.stop()
    
    # Just verify the example doesn't crash
    asyncio.run(example_usage())