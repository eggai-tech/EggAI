"""MCP adapter implementation for external tool integration."""

import logging
from typing import Dict, List, Any

from mcp import StdioServerParameters, ClientSession
from mcp.client.stdio import stdio_client

from adapter_base import BaseAdapter, ToolSchema, ToolResult

logger = logging.getLogger(__name__)


class MCPAdapter(BaseAdapter):
    """Adapter for Model Context Protocol servers."""
    
    def __init__(self, adapter_name: str, server_params: StdioServerParameters):
        super().__init__(adapter_name)
        self.server_params = server_params
        self.connection = None
        self.session = None

    async def initialize_backend(self):
        """Initialize MCP server connection."""
        logger.info(f"Connecting to MCP server: {self.server_params.command} {' '.join(self.server_params.args)}")
        
        self.connection = stdio_client(self.server_params)
        read, write = await self.connection.__aenter__()
        
        self.session = ClientSession(read, write)
        await self.session.__aenter__()
        await self.session.initialize()
        
        logger.info("MCP server connection established")

    async def discover_tools(self) -> List[ToolSchema]:
        """Discover tools from MCP server."""
        if not self.session:
            raise RuntimeError("MCP session not initialized")
            
        tools_response = await self.session.list_tools()
        tool_schemas = []
        
        for mcp_tool in tools_response.tools:
            schema = ToolSchema(
                name=mcp_tool.name,
                description=mcp_tool.description,
                parameters=mcp_tool.inputSchema if hasattr(mcp_tool, 'inputSchema') else {}
            )
            tool_schemas.append(schema)
            
        logger.info(f"Discovered {len(tool_schemas)} MCP tools")
        return tool_schemas

    async def execute_tool(self, tool_name: str, parameters: Dict[str, Any]) -> ToolResult:
        """Execute MCP tool."""
        if not self.session:
            raise RuntimeError("MCP session not initialized")
            
        try:
            logger.info(f"Executing MCP tool: {tool_name} with params: {parameters}")
            result = await self.session.call_tool(tool_name, parameters)
            
            # MCP tools return a list of content items
            if hasattr(result, 'content') and result.content:
                content = result.content[0]
                if hasattr(content, 'text'):
                    return ToolResult(True, content.text)
                else:
                    return ToolResult(True, str(content))
            else:
                return ToolResult(True, "Tool executed successfully")
                
        except Exception as e:
            logger.error(f"MCP tool execution failed: {e}")
            return ToolResult(False, None, str(e))

    async def cleanup_backend(self):
        """Clean up MCP connections."""
        if self.session:
            try:
                await self.session.__aexit__(None, None, None)
            except Exception as e:
                logger.warning(f"Error closing MCP session: {e}")
                
        if self.connection:
            try:
                await self.connection.__aexit__(None, None, None)
            except Exception as e:
                logger.warning(f"Error closing MCP connection: {e}")


def create_filesystem_adapter() -> MCPAdapter:
    """Create adapter for filesystem MCP server."""  
    return MCPAdapter(
        "FileSystem", 
        StdioServerParameters(
            command="npx",
            args=["-y", "@modelcontextprotocol/server-filesystem", "sandbox"]
        )
    )


if __name__ == "__main__":
    from adapter_base import run_adapter
    
    # Example: Run filesystem adapter as standalone process
    adapter = create_filesystem_adapter()
    run_adapter(adapter)