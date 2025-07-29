"""Agent-to-Agent (A2A) Protocol Implementation

This module provides A2A protocol compliant communication between EggAI agents,
following the official A2A specification at https://a2a-protocol.org/

Key features:
- JSON-RPC 2.0 over HTTP(S)
- Agent discovery via well-known URIs
- Task management with stateful operations
- Standards compliant message handling
"""

from .server import A2AServer
from .client import A2AClient, RemoteAgent
from .types import (
    AgentCard, Task, TaskStatus, Message, MessageRole, Part, PartType,
    JsonRpcRequest, JsonRpcResponse, JsonRpcError
)

__all__ = [
    "A2AServer", "A2AClient", "RemoteAgent",
    "AgentCard", "Task", "TaskStatus", "Message", "MessageRole", "Part", "PartType",
    "JsonRpcRequest", "JsonRpcResponse", "JsonRpcError"
]