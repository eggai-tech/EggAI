"""API Adapter for Static Tool Configuration

This module provides an adapter that loads tool definitions from JSON configuration
rather than discovering them dynamically. Useful for REST APIs and services with
known, static tool definitions.

The adapter accepts JSON configuration specifying tools, their parameters,
descriptions, and expected outputs.
"""

import asyncio
import json
import logging
from typing import Dict, List, Any, Optional
import aiohttp

from adapter_base import BaseAdapter, ToolSchema, ToolResult

logger = logging.getLogger(__name__)


class APIAdapter(BaseAdapter):
    """Adapter for REST API services with static tool configuration.
    
    This adapter loads tool definitions from a JSON configuration file
    and provides a REST API interface for tool execution.
    
    JSON Configuration Format:
    {
        "tools": [
            {
                "name": "tool_name",
                "description": "Tool description",
                "endpoint": "/api/endpoint",
                "method": "POST",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "param1": {"type": "string", "description": "Parameter 1"},
                        "param2": {"type": "number", "description": "Parameter 2"}
                    },
                    "required": ["param1"]
                },
                "output": {
                    "type": "object",
                    "properties": {
                        "result": {"type": "string", "description": "Result value"}
                    }
                }
            }
        ]
    }
    """
    
    def __init__(self, adapter_name: str, config_path: str, base_url: str, 
                 headers: Optional[Dict[str, str]] = None):
        """Initialize the API adapter.
        
        Args:
            adapter_name: Name identifier for this adapter
            config_path: Path to JSON configuration file
            base_url: Base URL for the API service
            headers: Optional HTTP headers for requests
        """
        super().__init__(adapter_name)
        self.config_path = config_path
        self.base_url = base_url.rstrip('/')
        self.headers = headers or {}
        self.tools_config = []
        self.session = None
        
    async def initialize_backend(self):
        """Initialize the API backend by loading configuration and creating HTTP session."""
        logger.info(f"Loading API configuration from {self.config_path}")
        
        try:
            with open(self.config_path, 'r') as f:
                config = json.load(f)
                self.tools_config = config.get('tools', [])
        except Exception as e:
            logger.error(f"Failed to load API configuration: {e}")
            raise
            
        # Create HTTP session
        self.session = aiohttp.ClientSession(
            headers=self.headers,
            timeout=aiohttp.ClientTimeout(total=30)
        )
        
        logger.info(f"API adapter initialized with {len(self.tools_config)} tools")
        
    async def discover_tools(self) -> List[ToolSchema]:
        """Discover tools from static JSON configuration.
        
        Returns:
            List of ToolSchema objects from the configuration
        """
        tools = []
        
        for tool_config in self.tools_config:
            try:
                tool = ToolSchema(
                    name=tool_config['name'],
                    description=tool_config['description'],
                    parameters=tool_config.get('parameters', {}),
                    output=tool_config.get('output', {})
                )
                tools.append(tool)
                logger.debug(f"Loaded tool: {tool.name}")
                
            except KeyError as e:
                logger.error(f"Invalid tool configuration missing {e}: {tool_config}")
                continue
                
        return tools
        
    async def execute_tool(self, tool_name: str, parameters: Dict[str, Any]) -> ToolResult:
        """Execute a tool by making HTTP request to configured endpoint.
        
        Args:
            tool_name: Name of the tool to execute
            parameters: Parameters to pass to the tool
            
        Returns:
            ToolResult with execution outcome
        """
        # Find tool configuration
        tool_config = None
        for config in self.tools_config:
            if config['name'] == tool_name:
                tool_config = config
                break
                
        if not tool_config:
            return ToolResult(
                success=False,
                error=f"Tool {tool_name} not found in configuration"
            )
            
        try:
            # Build request
            endpoint = tool_config.get('endpoint', f'/{tool_name}')
            method = tool_config.get('method', 'POST').upper()
            url = f"{self.base_url}{endpoint}"
            
            # Make HTTP request
            async with self.session.request(
                method=method,
                url=url,
                json=parameters if method in ['POST', 'PUT', 'PATCH'] else None,
                params=parameters if method == 'GET' else None
            ) as response:
                
                if response.status == 200:
                    result = await response.json()
                    return ToolResult(success=True, result=result)
                else:
                    error_text = await response.text()
                    return ToolResult(
                        success=False,
                        error=f"HTTP {response.status}: {error_text}"
                    )
                    
        except Exception as e:
            logger.error(f"Tool execution failed for {tool_name}: {e}")
            return ToolResult(
                success=False,
                error=f"Execution error: {str(e)}"
            )
            
    async def cleanup_backend(self):
        """Cleanup HTTP session and resources."""
        if self.session:
            await self.session.close()
            logger.info("API adapter session closed")

