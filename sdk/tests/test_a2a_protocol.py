"""Tests for A2A Protocol compliant implementation"""

import asyncio
import json
import pytest
from unittest.mock import patch, AsyncMock

from eggai import Agent
from eggai.transport import eggai_set_default_transport, InMemoryTransport
from eggai.a2a.types import (
    AgentCard, Task, TaskStatus, Message, MessageRole, Part, PartType,
    JsonRpcRequest, JsonRpcResponse
)

# Skip tests if FastAPI/httpx not available
try:
    import fastapi
    import httpx
    from eggai.a2a import A2AServer, A2AClient
    A2A_AVAILABLE = True
except ImportError:
    A2A_AVAILABLE = False


class TestA2ATypes:
    """Test A2A protocol types"""
    
    def test_agent_card_creation(self):
        """Test AgentCard creation and validation"""
        card = AgentCard(
            name="TestAgent",
            description="A test agent for A2A protocol",
            endpoint="http://localhost:8080"
        )
        
        assert card.name == "TestAgent"
        assert card.protocol_version == "0.2.6"
        assert card.endpoint == "http://localhost:8080"
        assert "none" in card.supported_auth
    
    def test_task_lifecycle(self):
        """Test Task creation and status transitions"""
        task = Task()
        
        assert task.status == TaskStatus.PENDING
        assert len(task.messages) == 0
        assert len(task.artifacts) == 0
        assert task.id is not None
    
    def test_message_structure(self):
        """Test A2A Message and Part structure"""
        part = Part(type=PartType.TEXT, content="Hello A2A!")
        message = Message(role=MessageRole.USER, parts=[part])
        
        assert message.role == MessageRole.USER
        assert len(message.parts) == 1
        assert message.parts[0].content == "Hello A2A!"
        assert message.parts[0].type == PartType.TEXT
    
    def test_jsonrpc_request(self):
        """Test JSON-RPC 2.0 request structure"""
        request = JsonRpcRequest(
            method="message/send",
            params={"test": "data"},
            id="123"
        )
        
        assert request.jsonrpc == "2.0"
        assert request.method == "message/send"
        assert request.params == {"test": "data"}
        assert request.id == "123"


@pytest.mark.skipif(not A2A_AVAILABLE, reason="FastAPI/httpx not available")
class TestA2AServer:
    """Test A2A Protocol server implementation"""
    
    @pytest.mark.asyncio
    async def test_server_creation(self):
        """Test A2AServer creation"""
        eggai_set_default_transport(lambda: InMemoryTransport())
        
        agent = Agent("A2AServerTest")
        server = A2AServer(agent, port=8081)
        
        assert server.agent == agent
        assert server.port == 8081
        assert server.agent_card.name == "A2AServerTest"
        assert server.agent_card.protocol_version == "0.2.6"
    
    @pytest.mark.asyncio
    async def test_agent_card_endpoint(self):
        """Test agent card well-known URI endpoint"""
        eggai_set_default_transport(lambda: InMemoryTransport())
        
        agent = Agent("CardTestAgent")
        server = A2AServer(agent, port=8082)
        
        # Test that the route exists
        routes = [route.path for route in server.app.routes if hasattr(route, 'path')]
        assert "/.well-known/agent.json" in routes
    
    @pytest.mark.asyncio
    async def test_jsonrpc_endpoint(self):
        """Test JSON-RPC endpoint exists"""
        eggai_set_default_transport(lambda: InMemoryTransport())
        
        agent = Agent("JsonRpcTestAgent")
        server = A2AServer(agent, port=8083)
        
        # Test that the main endpoint exists
        routes = [route.path for route in server.app.routes if hasattr(route, 'path')]
        assert "/" in routes


@pytest.mark.skipif(not A2A_AVAILABLE, reason="FastAPI/httpx not available")
class TestA2AClient:
    """Test A2A Protocol client implementation"""
    
    @pytest.mark.asyncio
    async def test_client_creation(self):
        """Test A2AClient creation"""
        client = A2AClient("http://localhost:8080")
        
        assert client.endpoint == "http://localhost:8080"
        assert client.timeout == 30.0
        await client.close()
    
    @pytest.mark.asyncio
    async def test_client_context_manager(self):
        """Test A2AClient as context manager"""
        async with A2AClient("http://localhost:8080") as client:
            assert client.endpoint == "http://localhost:8080"


class TestA2AIntegration:
    """Test A2A protocol integration with EggAI agents"""
    
    @pytest.mark.asyncio
    async def test_agent_to_a2a_method(self):
        """Test agent.to_a2a() method exists and handles dependencies"""
        eggai_set_default_transport(lambda: InMemoryTransport())
        
        agent = Agent("IntegrationTestAgent")
        
        # Should fail gracefully without FastAPI
        with patch.dict('sys.modules', {'fastapi': None}):
            with pytest.raises(ImportError, match="A2A functionality requires"):
                await agent.to_a2a()
    
    def test_a2a_protocol_compliance(self):
        """Test that our implementation follows A2A protocol standards"""
        # Test protocol version
        card = AgentCard(name="Test", description="Test", endpoint="http://test")
        assert card.protocol_version == "0.2.6"
        
        # Test JSON-RPC 2.0 compliance
        request = JsonRpcRequest(method="test", id="1")
        assert request.jsonrpc == "2.0"
        
        # Test task states match A2A spec
        valid_statuses = {"pending", "running", "completed", "failed", "cancelled"}
        a2a_statuses = {status.value for status in TaskStatus}
        assert a2a_statuses == valid_statuses
        
        # Test message roles match A2A spec
        valid_roles = {"user", "assistant", "system"}
        a2a_roles = {role.value for role in MessageRole}
        assert a2a_roles == valid_roles
        
        # Test part types
        valid_types = {"text", "file", "data"}
        a2a_types = {ptype.value for ptype in PartType}
        assert a2a_types == valid_types


@pytest.mark.skipif(not A2A_AVAILABLE, reason="FastAPI/httpx not available")
class TestA2AProtocolMethods:
    """Test A2A protocol method implementations"""
    
    @pytest.mark.asyncio
    async def test_message_send_structure(self):
        """Test message/send method parameter structure"""
        from eggai.a2a.types import MessageSendParams
        
        part = Part(type=PartType.TEXT, content="Test message")
        message = Message(role=MessageRole.USER, parts=[part])
        params = MessageSendParams(messages=[message])
        
        # Verify structure matches A2A spec
        assert params.messages[0].role == MessageRole.USER
        assert params.messages[0].parts[0].type == PartType.TEXT
        assert params.messages[0].parts[0].content == "Test message"
    
    @pytest.mark.asyncio
    async def test_task_operations_structure(self):
        """Test tasks/get and tasks/cancel parameter structure"""
        from eggai.a2a.types import TasksGetParams, TasksCancelParams
        
        get_params = TasksGetParams(task_id="test-123")
        cancel_params = TasksCancelParams(task_id="test-456")
        
        assert get_params.task_id == "test-123"
        assert cancel_params.task_id == "test-456"