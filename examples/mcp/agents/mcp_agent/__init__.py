"""MCP Agent package for EggAI with DSPy ReAct integration."""

from .agent import run_mcp_agent
from .mcp_manager import MCPManager
from .signature import MCPAgentSignature
from .status_provider import MCPToolStatusProvider

__all__ = [
    "run_mcp_agent",
    "MCPManager", 
    "MCPAgentSignature",
    "MCPToolStatusProvider"
]