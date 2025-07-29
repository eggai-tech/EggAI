"""A2A Protocol compliant type definitions"""

from typing import Dict, Any, List, Optional, Union, Literal
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum
import uuid


class TaskStatus(str, Enum):
    """Task status as per A2A specification"""
    PENDING = "pending"
    RUNNING = "running" 
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class MessageRole(str, Enum):
    """Message roles as per A2A specification"""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class PartType(str, Enum):
    """Content part types"""
    TEXT = "text"
    FILE = "file"
    DATA = "data"


class Part(BaseModel):
    """A2A Protocol Part - fundamental content unit"""
    type: PartType
    content: Union[str, Dict[str, Any]]
    metadata: Optional[Dict[str, Any]] = None


class Message(BaseModel):
    """A2A Protocol Message"""
    role: MessageRole
    parts: List[Part]
    metadata: Optional[Dict[str, Any]] = None


class Task(BaseModel):
    """A2A Protocol Task"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    status: TaskStatus = TaskStatus.PENDING
    messages: List[Message] = Field(default_factory=list)
    artifacts: List[Dict[str, Any]] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    metadata: Optional[Dict[str, Any]] = None


class AgentCard(BaseModel):
    """A2A Protocol Agent Card - agent discovery metadata"""
    name: str
    description: str
    version: str = "1.0.0"
    protocol_version: str = "0.2.6"
    endpoint: str
    capabilities: List[str] = Field(default_factory=list)
    supported_auth: List[str] = Field(default_factory=lambda: ["none"])
    metadata: Optional[Dict[str, Any]] = None


# JSON-RPC 2.0 Types
class JsonRpcRequest(BaseModel):
    """JSON-RPC 2.0 Request"""
    jsonrpc: str = "2.0"
    method: str
    params: Optional[Dict[str, Any]] = None
    id: Optional[Union[str, int]] = None


class JsonRpcError(BaseModel):
    """JSON-RPC 2.0 Error"""
    code: int
    message: str
    data: Optional[Any] = None


class JsonRpcResponse(BaseModel):
    """JSON-RPC 2.0 Response"""
    jsonrpc: str = "2.0"
    result: Optional[Any] = None
    error: Optional[JsonRpcError] = None
    id: Optional[Union[str, int]] = None


# A2A Method Parameters
class MessageSendParams(BaseModel):
    """Parameters for message/send method"""
    messages: List[Message]
    task_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class MessageStreamParams(BaseModel):
    """Parameters for message/stream method"""
    messages: List[Message]
    task_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class TasksGetParams(BaseModel):
    """Parameters for tasks/get method"""
    task_id: str


class TasksCancelParams(BaseModel):
    """Parameters for tasks/cancel method"""  
    task_id: str


# A2A Method Results
class MessageSendResult(BaseModel):
    """Result for message/send method"""
    task: Task


class TasksGetResult(BaseModel):
    """Result for tasks/get method"""
    task: Task


class TasksCancelResult(BaseModel):
    """Result for tasks/cancel method"""
    task: Task