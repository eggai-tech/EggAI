"""DSPy Tool Integration Module

This module provides integration between external tools discovered via MCP adapters
and DSPy's tool system. It handles the conversion of async external tool calls
to synchronous DSPy-compatible tools with proper parameter extraction.

Key responsibilities:
- Convert ExternalTool objects to dspy.Tool objects
- Handle async/sync compatibility for tool execution
- Extract and normalize tool parameters from DSPy's parameter wrapping
- Provide error handling and logging for tool execution
"""

import asyncio
import logging
from typing import List, Dict, Any
import dspy

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from agent_integration import ExternalTool, call_external_tool

logger = logging.getLogger(__name__)


def create_dspy_tools(external_tools: List[ExternalTool]) -> List[dspy.Tool]:
    """Convert external tools to DSPy-compatible tools.
    
    This function takes a list of ExternalTool objects (discovered from MCP adapters)
    and converts them into dspy.Tool objects that can be used by DSPy's ReAct system.
    
    The conversion process handles:
    1. Async to sync conversion (DSPy tools must be synchronous)
    2. Parameter extraction and normalization
    3. JSON Schema to DSPy args format conversion
    4. Error handling and result formatting
    
    Args:
        external_tools: List of ExternalTool objects from MCP adapter discovery
        
    Returns:
        List of dspy.Tool objects ready for use in DSPy ReAct
    """
    dspy_tools = []
    
    for ext_tool in external_tools:
        def create_tool_func(tool):
            """Create an async wrapper for the external tool call."""
            async def tool_func(**kwargs):
                try:
                    result = await call_external_tool(
                        tool.adapter_name,
                        tool.name, 
                        kwargs
                    )
                    return str(result)
                except Exception as e:
                    logger.error(f"Tool {tool.name} execution failed: {e}")
                    return f"Error: {str(e)}"
            return tool_func
        
        tool_func = create_tool_func(ext_tool)
        
        def create_sync_wrapper(tool, async_func):
            """Create a synchronous wrapper for the async tool function.
            
            DSPy requires synchronous tool functions, but our external tools are async.
            This wrapper handles the async/sync conversion and parameter extraction.
            
            DSPy sometimes wraps parameters in a 'kwargs' dictionary, so we need to
            extract the actual parameters before passing them to the tool.
            """
            def sync_wrapper(**kwargs):
                # Extract actual parameters from DSPy's parameter wrapping
                if 'kwargs' in kwargs and isinstance(kwargs['kwargs'], dict):
                    actual_params = kwargs['kwargs']
                else:
                    actual_params = kwargs
                
                try:
                    # Handle async execution in sync context
                    try:
                        loop = asyncio.get_running_loop()
                        # We're in an async context, so run in a separate thread with new event loop
                        import concurrent.futures
                        
                        def run_in_new_loop():
                            new_loop = asyncio.new_event_loop()
                            asyncio.set_event_loop(new_loop)
                            try:
                                return new_loop.run_until_complete(async_func(**actual_params))
                            finally:
                                new_loop.close()
                        
                        with concurrent.futures.ThreadPoolExecutor() as executor:
                            future = executor.submit(run_in_new_loop)
                            return future.result(timeout=30)
                            
                    except RuntimeError:
                        # No event loop running, can use asyncio.run directly
                        return asyncio.run(async_func(**actual_params))
                        
                except Exception as e:
                    logger.error(f"Tool {tool.name} wrapper error: {e}")
                    return f"Error: {str(e)}"
            return sync_wrapper
        
        sync_wrapper = create_sync_wrapper(ext_tool, tool_func)
        
        # Convert JSON Schema parameters to DSPy args format
        args_info = {}
        if isinstance(ext_tool.parameters, dict) and 'properties' in ext_tool.parameters:
            for param_name, param_info in ext_tool.parameters['properties'].items():
                if isinstance(param_info, dict):
                    desc = param_info.get('description', f'Parameter {param_name}')
                    param_type = param_info.get('type', 'string')
                    args_info[param_name] = f"{desc} (type: {param_type})"
                else:
                    args_info[param_name] = f"Parameter {param_name}"
        
        # Create the DSPy tool object
        try:
            dspy_tool = dspy.Tool(
                func=sync_wrapper,
                name=ext_tool.name,
                desc=ext_tool.description,
                args=args_info
            )
            dspy_tools.append(dspy_tool)
            
        except Exception as e:
            logger.error(f"Failed to create DSPy tool {ext_tool.name}: {e}")
    
    return dspy_tools


