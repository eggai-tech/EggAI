"""External Tools Integration Module

This module provides a standalone integration layer for external tools accessed via
MCP (Model Context Protocol) adapters. It handles tool discovery, caching, and
execution through Kafka-based messaging.

Key components:
- ExternalTool: Wrapper class for external tools with metadata
- Tool discovery: Async discovery of tools from MCP adapters
- Tool execution: Background manager for handling tool calls
- Caching: Local cache for discovered tools to avoid repeated discovery

The module uses a persistent background agent to handle tool call responses
and maintains proper async/sync boundaries for integration with various frameworks.
"""

import asyncio
import logging
from typing import Dict, List, Any, Optional
import uuid
import time

from eggai import Agent, Channel
from eggai.schemas import Message

logger = logging.getLogger(__name__)


class ExternalTool:
    """Represents an external tool accessible via MCP adapters.
    
    This class wraps external tool metadata and provides a consistent interface
    for tool execution. Tools are discovered from MCP adapters and cached locally.
    
    Attributes:
        name: Tool name as defined by the adapter
        description: Human-readable description of tool functionality
        parameters: JSON Schema describing expected parameters
        adapter_name: Name of the adapter hosting this tool
    """
    
    def __init__(self, name: str, description: str, parameters: Dict[str, Any], adapter_name: str):
        self.name = name
        self.description = description
        self.parameters = parameters
        self.adapter_name = adapter_name

    async def call(self, **kwargs) -> Any:
        """Execute this tool via its adapter with the given parameters."""
        return await call_external_tool(self.adapter_name, self.name, kwargs)


# Global state for tool discovery and caching
_tool_cache: Dict[str, List[ExternalTool]] = {}
_discovery_lock = asyncio.Lock()


async def discover_tools(adapter_names: List[str], source_id: Optional[str] = None, timeout: float = 10.0) -> Dict[str, List[ExternalTool]]:
    """Discover tools from specified MCP adapters.
    
    This function sends discovery requests to MCP adapters via Kafka messaging
    and waits for responses containing tool definitions. Results are cached
    to avoid repeated discovery calls.
    
    Args:
        adapter_names: List of adapter names to discover tools from
        source_id: Optional identifier for the request (auto-generated if None)
        timeout: Maximum time to wait for discovery responses in seconds
        
    Returns:
        Dictionary mapping adapter names to their discovered tools
        
    Raises:
        asyncio.TimeoutError: If discovery request times out
    """
    async with _discovery_lock:
        if source_id is None:
            source_id = f"discovery-{uuid.uuid4().hex[:8]}"
        
        logger.info(f"Discovering tools from adapters: {adapter_names}")
        
        # Set up response listener
        response_channel = Channel("tools.list.response")
        discovery_results: Dict[str, asyncio.Future] = {}
        received_responses = []
        
        # Pre-create a completed future outside the callback
        completed_future = asyncio.Future()
        completed_future.set_result(None)
        
        def handle_response(msg_dict: Dict[str, Any]):
            # Convert dict back to Message for compatibility
            msg = Message(**msg_dict)
            logger.debug(f"Received discovery response: {msg.type}")
            if msg.type == "tools_list_response":
                adapter_name = msg.data.get("adapter_name")
                if adapter_name in discovery_results:
                    tools_data = msg.data.get("tools", [])
                    logger.info(f"Received {len(tools_data)} tools from {adapter_name}")
                    
                    tools = []
                    for tool_data in tools_data:
                        tool = ExternalTool(
                            name=tool_data["name"],
                            description=tool_data["description"], 
                            parameters=tool_data["parameters"],
                            adapter_name=adapter_name
                        )
                        tools.append(tool)
                    
                    _tool_cache[adapter_name] = tools
                    logger.debug(f"Cached {len(tools)} tools from {adapter_name}")
                    
                    if not discovery_results[adapter_name].done():
                        discovery_results[adapter_name].set_result(tools)
                    received_responses.append(msg)
            
            # Return the pre-created completed future
            return completed_future
        
        subscription_active = True
        
        def filtered_handle_response(msg_dict: Dict[str, Any]):
            if subscription_active:
                return handle_response(msg_dict)
            else:
                return completed_future
        
        # Subscribe to the general response channel
        general_response_channel = Channel("tools.list.response")
        await general_response_channel.subscribe(filtered_handle_response)
        
        try:
            # Create discovery futures
            for adapter_name in adapter_names:
                discovery_results[adapter_name] = asyncio.Future()
            
            # Send discovery requests
            for adapter_name in adapter_names:
                list_channel = Channel(f"tools.list.{adapter_name.lower()}")
                request = Message(
                    type="tools_list_request",
                    source=source_id,
                    data={"action": "list_tools"}
                )
                logger.debug(f"Requesting tools from {adapter_name} on channel {list_channel.get_name()}")
                await list_channel.publish(request)
            
            # Wait for all discoveries to complete
            discovery_tasks = [
                asyncio.wait_for(discovery_results[name], timeout=timeout) 
                for name in adapter_names
            ]
            results = await asyncio.gather(*discovery_tasks, return_exceptions=True)
            
            # Log any timeouts or errors
            for i, result in enumerate(results):
                if isinstance(result, asyncio.TimeoutError):
                    logger.error(f"Tool discovery timed out for {adapter_names[i]}")
                elif isinstance(result, Exception):
                    logger.error(f"Tool discovery failed for {adapter_names[i]}: {result}")
            
            logger.info("Tool discovery completed")
            return {name: _tool_cache.get(name, []) for name in adapter_names}
            
        finally:
            # Disable subscription handling
            subscription_active = False


# Global persistent tool call manager
_tool_call_manager: Optional['ToolCallManager'] = None
_manager_lock = asyncio.Lock()


class ToolCallManager:
    """Persistent background manager for tool call responses using asyncio.Queue."""
    
    def __init__(self):
        self.agent = None
        self.response_queue = asyncio.Queue()
        self.pending_calls: Dict[str, asyncio.Future] = {}
        self.running = False
        self._task = None
    
    async def start(self):
        """Start the persistent background task."""
        if self.running:
            return
        
        self.agent = Agent("ToolCallManager")
        self.running = True
        
        # Set up persistent subscription
        @self.agent.subscribe(Channel("tools.call.response"))
        async def handle_tool_response(msg: Message):
            logger.info(f"🔔 Background manager received tool response: {msg.type}")
            if msg.type == "tool_call_response":
                await self.response_queue.put(msg)
        
        # Start agent and background task
        await self.agent.start()
        self._task = asyncio.create_task(self._process_responses())
        logger.info("✅ ToolCallManager started with persistent agent")
    
    async def _process_responses(self):
        """Background task to process tool call responses."""
        while self.running:
            try:
                # Wait for responses indefinitely
                msg = await self.response_queue.get()
                
                call_id = msg.data.get("call_id")
                tool_name = msg.data.get("tool_name")
                request_timestamp = msg.data.get("timestamp")
                
                if request_timestamp:
                    latency = time.time() - request_timestamp
                    logger.info(f"📨 Processing tool response for {tool_name} (latency: {latency:.2f}s)")
                
                if call_id and call_id in self.pending_calls:
                    future = self.pending_calls[call_id]
                    result_data = msg.data.get("result", {})
                    
                    if result_data.get("success"):
                        logger.info(f"✅ Tool call successful: {tool_name}")
                        if not future.done():
                            future.set_result(result_data.get("result"))
                    else:
                        error = result_data.get("error", "Unknown error")
                        logger.error(f"❌ Tool call failed: {tool_name} - {error}")
                        if not future.done():
                            future.set_exception(Exception(error))
                    
                    del self.pending_calls[call_id]
                    logger.info(f"🧹 Cleaned up call_id: {call_id}")
                elif call_id:
                    logger.warning(f"⚠️ Received response for unknown call_id: {call_id}")
                else:
                    logger.error(f"❌ Received response with no call_id")
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error processing tool response: {e}")
    
    async def call_tool(self, adapter_name: str, tool_name: str, parameters: Dict[str, Any], 
                       source_id: str, timeout: float) -> Any:
        """Execute a tool call and wait for the response.
        
        Sends a tool call request to the specified adapter and waits for the response.
        The call is tracked using a unique call_id to match requests with responses.
        
        Args:
            adapter_name: Name of the adapter hosting the tool
            tool_name: Name of the tool to execute
            parameters: Parameters to pass to the tool
            source_id: Identifier for the calling agent
            timeout: Maximum time to wait for response
            
        Returns:
            The tool execution result
            
        Raises:
            Exception: If the tool call times out or fails
        """
        call_id = str(uuid.uuid4())
        call_timestamp = time.time()
        result_future = asyncio.Future()
        
        # Register the pending call
        self.pending_calls[call_id] = result_future
        
        # Send tool call request
        call_channel = Channel(f"tools.call.{adapter_name.lower()}")
        request = Message(
            type="tool_call_request",
            source=source_id,
            data={
                "action": "call_tool",
                "name": tool_name,
                "parameters": parameters,
                "call_id": call_id,
                "timestamp": call_timestamp
            }
        )
        
        logger.debug(f"Calling tool: {adapter_name}.{tool_name}")
        await call_channel.publish(request)
        
        try:
            result = await asyncio.wait_for(result_future, timeout=timeout)
            return result
        except asyncio.TimeoutError:
            if call_id in self.pending_calls:
                del self.pending_calls[call_id]
            logger.error(f"Tool call timeout after {timeout}s: {adapter_name}.{tool_name}")
            raise Exception(f"Tool call timeout: {adapter_name}.{tool_name}")
    
    async def stop(self):
        """Stop the background manager and cleanup resources."""
        if self.running:
            self.running = False
            if self._task:
                self._task.cancel()
                try:
                    await self._task
                except asyncio.CancelledError:
                    pass
            if self.agent:
                await self.agent.stop()
            logger.info("ToolCallManager stopped")


async def _get_tool_call_manager() -> ToolCallManager:
    """Get or create the global tool call manager."""
    global _tool_call_manager
    
    async with _manager_lock:
        if _tool_call_manager is None:
            _tool_call_manager = ToolCallManager()
            await _tool_call_manager.start()
        return _tool_call_manager


async def call_external_tool(adapter_name: str, tool_name: str, parameters: Dict[str, Any], 
                           source_id: Optional[str] = None, timeout: float = 10.0) -> Any:
    """
    Standalone tool calling using persistent background manager.
    
    Args:
        adapter_name: Name of the adapter hosting the tool
        tool_name: Name of the tool to call
        parameters: Parameters to pass to the tool
        source_id: Optional source identifier for the request (defaults to unique ID)
        timeout: Timeout for the tool call in seconds
        
    Returns:
        Tool execution result
    """
    if source_id is None:
        source_id = f"caller-{uuid.uuid4().hex[:8]}"
    
    # Get the persistent manager
    manager = await _get_tool_call_manager()
    
    # Use the manager to make the call
    return await manager.call_tool(adapter_name, tool_name, parameters, source_id, timeout)


def get_cached_tools(adapter_name: Optional[str] = None) -> List[ExternalTool]:
    """
    Get cached tools from previous discovery calls.
    
    Args:
        adapter_name: Optional adapter name filter. If None, returns all cached tools.
        
    Returns:
        List of cached tools
    """
    if adapter_name:
        return _tool_cache.get(adapter_name, [])
    else:
        all_tools = []
        for tools in _tool_cache.values():
            all_tools.extend(tools)
        return all_tools


def clear_tool_cache(adapter_name: Optional[str] = None):
    """
    Clear cached tools.
    
    Args:
        adapter_name: Optional adapter name to clear. If None, clears all cached tools.
    """
    if adapter_name:
        _tool_cache.pop(adapter_name, None)
        logger.info(f"🧹 Cleared tool cache for {adapter_name}")
    else:
        _tool_cache.clear()
        logger.info(f"🧹 Cleared all tool cache")




# DSPy integration
def external_tools_to_dspy_tools(external_tools: List[ExternalTool]):
    """Convert external tools to DSPy-compatible tools."""
    try:
        import dspy
    except ImportError:
        logger.warning("DSPy not available - cannot create DSPy tools")
        return []
    
    dspy_tools = []
    for ext_tool in external_tools:
        def create_tool_func(tool):
            async def tool_func(**kwargs):
                return await call_external_tool(
                    tool.adapter_name, 
                    tool.name, 
                    kwargs
                )
            return tool_func
        
        # Create DSPy tool (assuming dspy.Tool exists)
        if hasattr(dspy, 'Tool'):
            dspy_tool = dspy.Tool(
                func=create_tool_func(ext_tool),
                name=ext_tool.name,
                desc=ext_tool.description
            )
            dspy_tools.append(dspy_tool)
    
    return dspy_tools


# Integration helper for standalone usage
async def setup_external_tools(adapter_names: List[str], source_id: Optional[str] = None) -> List[ExternalTool]:
    """
    Standalone helper to discover and cache external tools.
    
    Args:
        adapter_names: List of adapter names to discover tools from
        source_id: Optional source identifier for the request
        
    Returns:
        List of all discovered tools
    """
    tools_by_adapter = await discover_tools(adapter_names, source_id)
    all_tools = []
    for tools in tools_by_adapter.values():
        all_tools.extend(tools)
    
    logger.info(f"External tools setup complete")
    logger.info(f"Available tools: {[tool.name for tool in all_tools]}")
    
    return all_tools


async def shutdown_tool_call_manager():
    """Shutdown the global tool call manager."""
    global _tool_call_manager
    
    async with _manager_lock:
        if _tool_call_manager is not None:
            manager = _tool_call_manager
            _tool_call_manager = None
            await manager.stop()
            logger.info("🛑 Global ToolCallManager shut down")