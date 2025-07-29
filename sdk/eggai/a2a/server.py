"""A2A Protocol compliant server implementation"""

import asyncio
import json
from datetime import datetime
from typing import Dict, Any, Optional

try:
    from fastapi import FastAPI, HTTPException, Request
    from fastapi.responses import JSONResponse, StreamingResponse
    import uvicorn
    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False

from .types import (
    AgentCard, Task, TaskStatus, Message, MessageRole, Part, PartType,
    JsonRpcRequest, JsonRpcResponse, JsonRpcError,
    MessageSendParams, MessageSendResult, TasksGetParams, TasksGetResult,
    TasksCancelParams, TasksCancelResult
)


class A2AServer:
    """A2A Protocol compliant server for EggAI agents"""
    
    def __init__(self, agent, host: str = "0.0.0.0", port: int = 8080, description: str = None):
        if not FASTAPI_AVAILABLE:
            raise ImportError("FastAPI is required for A2A functionality. Install with: pip install fastapi uvicorn")
        
        self.agent = agent
        self.host = host
        self.port = port
        self.description = description or f"EggAI Agent: {agent._name}"
        
        # A2A state management
        self.tasks: Dict[str, Task] = {}
        
        # Create Agent Card
        self.agent_card = AgentCard(
            name=agent._name,
            description=self.description,
            endpoint=f"http://{host}:{port}",
            capabilities=["message_handling", "task_management"],
            metadata={"framework": "eggai"}
        )
        
        self.app = FastAPI(title=f"A2A Agent: {agent._name}", version="1.0.0")
        self._setup_routes()
    
    def _setup_routes(self):
        """Setup A2A protocol routes"""
        
        @self.app.get("/.well-known/agent.json")
        async def get_agent_card():
            """A2A Agent Discovery - Well-known URI"""
            return self.agent_card.dict()
        
        @self.app.post("/")
        async def handle_jsonrpc(request: Request):
            """A2A JSON-RPC 2.0 endpoint"""
            try:
                body = await request.body()
                data = json.loads(body)
                rpc_request = JsonRpcRequest(**data)
                
                # Route to appropriate handler
                if rpc_request.method == "message/send":
                    result = await self._handle_message_send(rpc_request)
                elif rpc_request.method == "tasks/get":
                    result = await self._handle_tasks_get(rpc_request)
                elif rpc_request.method == "tasks/cancel":
                    result = await self._handle_tasks_cancel(rpc_request)
                else:
                    # Method not found
                    response = JsonRpcResponse(
                        id=rpc_request.id,
                        error=JsonRpcError(
                            code=-32601,
                            message="Method not found",
                            data={"method": rpc_request.method}
                        )
                    )
                    return JSONResponse(response.dict(), status_code=200)
                
                return JSONResponse(result.dict(), status_code=200)
                
            except json.JSONDecodeError:
                response = JsonRpcResponse(
                    error=JsonRpcError(
                        code=-32700,
                        message="Parse error"
                    )
                )
                return JSONResponse(response.dict(), status_code=200)
            except Exception as e:
                response = JsonRpcResponse(
                    error=JsonRpcError(
                        code=-32603,
                        message="Internal error",
                        data=str(e)
                    )
                )
                return JSONResponse(response.dict(), status_code=200)
        
        @self.app.get("/health")
        async def health_check():
            """Health check endpoint"""
            return {"status": "healthy", "agent": self.agent._name}
    
    async def _handle_message_send(self, rpc_request: JsonRpcRequest) -> JsonRpcResponse:
        """Handle message/send A2A method"""
        try:
            params = MessageSendParams(**rpc_request.params)
            
            # Create or get task
            task_id = params.task_id or Task().id
            if task_id not in self.tasks:
                self.tasks[task_id] = Task(id=task_id)
            
            task = self.tasks[task_id]
            task.status = TaskStatus.RUNNING
            task.messages.extend(params.messages)
            task.updated_at = datetime.utcnow()
            
            # Process messages through the agent
            response_parts = []
            for message in params.messages:
                for part in message.parts:
                    if part.type == PartType.TEXT:
                        # Convert A2A message to EggAI format and publish
                        eggai_message = {
                            "content": part.content,
                            "role": message.role.value,
                            "task_id": task_id,
                            "a2a_metadata": message.metadata
                        }
                        
                        # Publish to agent's default channel
                        from eggai import Channel
                        channel = Channel("eggai.channel")
                        await channel.publish(eggai_message)
                        
                        # Create response (simple echo for minimal implementation)
                        response_parts.append(Part(
                            type=PartType.TEXT,
                            content=f"Processed: {part.content}"
                        ))
            
            # Add assistant response to task
            if response_parts:
                response_message = Message(
                    role=MessageRole.ASSISTANT,
                    parts=response_parts
                )
                task.messages.append(response_message)
            
            task.status = TaskStatus.COMPLETED
            task.updated_at = datetime.utcnow()
            
            result = MessageSendResult(task=task)
            return JsonRpcResponse(id=rpc_request.id, result=result.dict())
            
        except Exception as e:
            return JsonRpcResponse(
                id=rpc_request.id,
                error=JsonRpcError(
                    code=-32603,
                    message="Internal error in message/send",
                    data=str(e)
                )
            )
    
    async def _handle_tasks_get(self, rpc_request: JsonRpcRequest) -> JsonRpcResponse:
        """Handle tasks/get A2A method"""
        try:
            params = TasksGetParams(**rpc_request.params)
            
            if params.task_id not in self.tasks:
                return JsonRpcResponse(
                    id=rpc_request.id,
                    error=JsonRpcError(
                        code=-32602,
                        message="Task not found",
                        data={"task_id": params.task_id}
                    )
                )
            
            task = self.tasks[params.task_id]
            result = TasksGetResult(task=task)
            return JsonRpcResponse(id=rpc_request.id, result=result.dict())
            
        except Exception as e:
            return JsonRpcResponse(
                id=rpc_request.id,
                error=JsonRpcError(
                    code=-32603,
                    message="Internal error in tasks/get",
                    data=str(e)
                )
            )
    
    async def _handle_tasks_cancel(self, rpc_request: JsonRpcRequest) -> JsonRpcResponse:
        """Handle tasks/cancel A2A method"""
        try:
            params = TasksCancelParams(**rpc_request.params)
            
            if params.task_id not in self.tasks:
                return JsonRpcResponse(
                    id=rpc_request.id,
                    error=JsonRpcError(
                        code=-32602,
                        message="Task not found",
                        data={"task_id": params.task_id}
                    )
                )
            
            task = self.tasks[params.task_id]
            if task.status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]:
                return JsonRpcResponse(
                    id=rpc_request.id,
                    error=JsonRpcError(
                        code=-32602,
                        message="Task cannot be cancelled",
                        data={"task_id": params.task_id, "status": task.status}
                    )
                )
            
            task.status = TaskStatus.CANCELLED
            task.updated_at = datetime.utcnow()
            
            result = TasksCancelResult(task=task)
            return JsonRpcResponse(id=rpc_request.id, result=result.dict())
            
        except Exception as e:
            return JsonRpcResponse(
                id=rpc_request.id,
                error=JsonRpcError(
                    code=-32603,
                    message="Internal error in tasks/cancel",
                    data=str(e)
                )
            )
    
    async def start(self) -> "A2AServer":
        """Start the A2A server"""
        # Ensure the agent is started
        if not self.agent._started:
            await self.agent.start()
        
        # Start the FastAPI server
        config = uvicorn.Config(
            app=self.app,
            host=self.host,
            port=self.port,
            log_level="info"
        )
        server = uvicorn.Server(config)
        
        # Run server in background task
        self.server_task = asyncio.create_task(server.serve())
        
        print(f"A2A Server started for agent '{self.agent._name}' at http://{self.host}:{self.port}")
        print(f"Agent Card available at: http://{self.host}:{self.port}/.well-known/agent.json")
        return self
    
    async def stop(self):
        """Stop the A2A server"""
        if hasattr(self, 'server_task'):
            self.server_task.cancel()
            try:
                await self.server_task
            except asyncio.CancelledError:
                pass
        
        await self.agent.stop()
        print(f"A2A Server stopped for agent '{self.agent._name}'")
    
    def __repr__(self):
        return f"A2AServer(agent='{self.agent._name}', host='{self.host}', port={self.port})"