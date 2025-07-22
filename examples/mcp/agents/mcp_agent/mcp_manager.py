"""MCP server connection manager."""

from typing import List

import aioconsole
import dspy
from mcp import StdioServerParameters, ClientSession
from mcp.client.stdio import stdio_client


class MCPManager:
    """Manages MCP server connections and provides tools."""
    
    def __init__(self):
        self.connections = []
        self.sessions = []
        self.all_tools = []
        
    async def initialize(self, servers: List[tuple[str, StdioServerParameters]]):
        """Initialize MCP connections and tools."""
        for name, server_params in servers:
            stdio_conn = stdio_client(server_params)
            read, write = await stdio_conn.__aenter__()
            self.connections.append(stdio_conn)
            
            session = ClientSession(read, write)
            await session.__aenter__()
            self.sessions.append(session)
            
            await aioconsole.aprint(f"  📡 Connecting to {name} server...")
            await session.initialize()
            
            tools_response = await session.list_tools()
            await aioconsole.aprint(f"  ✅ {name}: {len(tools_response.tools)} tools loaded")
            
            for tool in tools_response.tools:
                self.all_tools.append(dspy.Tool.from_mcp_tool(session, tool))
        
        await aioconsole.aprint(f"🎉 Ready! {len(self.all_tools)} tools available")
    
    def get_tools(self):
        """Get all available tools."""
        return self.all_tools
    
    async def cleanup(self):
        """Clean up all connections."""
        for session in self.sessions:
            try:
                await session.__aexit__(None, None, None)
            except:
                pass
        
        for conn in self.connections:
            try:
                await conn.__aexit__(None, None, None)
            except:
                pass