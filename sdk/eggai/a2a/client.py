"""A2A Protocol compliant client implementation"""

import json
from typing import List, Optional

try:
    import httpx
    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False

from .types import (
    AgentCard, Task, Message, Part, PartType, MessageRole,
    JsonRpcRequest, JsonRpcResponse, MessageSendParams, MessageSendResult,
    TasksGetParams, TasksGetResult, TasksCancelParams, TasksCancelResult
)


class A2AClient:
    """A2A Protocol compliant client for communicating with remote agents"""
    
    def __init__(self, endpoint: str, timeout: float = 30.0):
        if not HTTPX_AVAILABLE:
            raise ImportError("httpx is required for A2A functionality. Install with: pip install httpx")
        
        self.endpoint = endpoint.rstrip('/')
        self.timeout = timeout
        self.client = httpx.AsyncClient(timeout=timeout)
    
    async def discover_agent(self) -> AgentCard:
        """Discover agent capabilities via well-known URI"""
        response = await self.client.get(f"{self.endpoint}/.well-known/agent.json")
        response.raise_for_status()
        return AgentCard(**response.json())
    
    async def send_message(
        self, 
        content: str, 
        role: MessageRole = MessageRole.USER,
        task_id: Optional[str] = None
    ) -> Task:
        """Send a text message to the remote agent"""
        # Create A2A message structure
        part = Part(type=PartType.TEXT, content=content)
        message = Message(role=role, parts=[part])
        params = MessageSendParams(messages=[message], task_id=task_id)
        
        # Create JSON-RPC request
        rpc_request = JsonRpcRequest(
            method="message/send",
            params=params.dict(),
            id="1"
        )
        
        # Send request
        response = await self.client.post(
            f"{self.endpoint}/",
            json=rpc_request.dict(),
            headers={"Content-Type": "application/json"}
        )
        response.raise_for_status()
        
        # Parse response
        rpc_response = JsonRpcResponse(**response.json())
        if rpc_response.error:
            raise Exception(f"A2A Error: {rpc_response.error.message}")
        
        result = MessageSendResult(**rpc_response.result)
        return result.task
    
    async def get_task(self, task_id: str) -> Task:
        """Get task status and results"""
        params = TasksGetParams(task_id=task_id)
        rpc_request = JsonRpcRequest(
            method="tasks/get",
            params=params.dict(),
            id="2"
        )
        
        response = await self.client.post(
            f"{self.endpoint}/",
            json=rpc_request.dict(),
            headers={"Content-Type": "application/json"}
        )
        response.raise_for_status()
        
        rpc_response = JsonRpcResponse(**response.json())
        if rpc_response.error:
            raise Exception(f"A2A Error: {rpc_response.error.message}")
        
        result = TasksGetResult(**rpc_response.result)
        return result.task
    
    async def cancel_task(self, task_id: str) -> Task:
        """Cancel a running task"""
        params = TasksCancelParams(task_id=task_id)
        rpc_request = JsonRpcRequest(
            method="tasks/cancel",
            params=params.dict(),
            id="3"
        )
        
        response = await self.client.post(
            f"{self.endpoint}/",
            json=rpc_request.dict(),
            headers={"Content-Type": "application/json"}
        )
        response.raise_for_status()
        
        rpc_response = JsonRpcResponse(**response.json())
        if rpc_response.error:
            raise Exception(f"A2A Error: {rpc_response.error.message}")
        
        result = TasksCancelResult(**rpc_response.result)
        return result.task
    
    async def health_check(self) -> bool:
        """Check if the remote agent is healthy"""
        try:
            response = await self.client.get(f"{self.endpoint}/health")
            return response.status_code == 200
        except Exception:
            return False
    
    async def close(self):
        """Close the HTTP client"""
        await self.client.aclose()
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
    
    def __repr__(self):
        return f"A2AClient(endpoint='{self.endpoint}')"


# Legacy alias for backward compatibility
RemoteAgent = A2AClient