"""Base adapter for external tool integration with eggai."""

import asyncio
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional
import json
from eggai import Agent, Channel
from eggai.schemas import Message
from eggai.transport import KafkaTransport, eggai_set_default_transport


class ToolSchema:
    """Standard tool schema representation."""
    
    def __init__(self, name: str, description: str, parameters: Dict[str, Any], output: Optional[Dict[str, Any]] = None):
        self.name = name
        self.description = description
        self.parameters = parameters  # JSON Schema for input
        self.output = output or {}    # JSON Schema for output

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
            "output": self.output
        }


class ToolResult:
    """Standard tool execution result."""
    
    def __init__(self, success: bool, result: Any = None, error: Optional[str] = None):
        self.success = success
        self.result = result
        self.error = error

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "result": self.result,
            "error": self.error
        }


class BaseAdapter(ABC):
    """Base class for external tool adapters."""
    
    def __init__(self, adapter_name: str):
        self.adapter_name = adapter_name
        # Use fixed agent name for stable consumer groups
        self.agent = Agent(f"{adapter_name}Adapter")
        self.list_channel = Channel(f"tools.list.{adapter_name.lower()}")
        self.call_channel = Channel(f"tools.call.{adapter_name.lower()}")
        self.response_channel = Channel("tools.list.response")
        self.call_response_channel = Channel("tools.call.response")
        self._tools_cache: List[ToolSchema] = []
        self._initialized = False

    @abstractmethod
    async def initialize_backend(self):
        """Initialize connection to external system (MCP server, API, etc.)."""
        pass

    @abstractmethod
    async def discover_tools(self) -> List[ToolSchema]:
        """Discover available tools from external system."""
        pass

    @abstractmethod
    async def execute_tool(self, tool_name: str, parameters: Dict[str, Any]) -> ToolResult:
        """Execute a tool with given parameters."""
        pass

    @abstractmethod
    async def cleanup_backend(self):
        """Clean up external system connections."""
        pass

    async def start(self):
        """Start the adapter service."""
        await self.initialize_backend()
        self._tools_cache = await self.discover_tools()
        
        @self.agent.subscribe(self.list_channel)
        async def handle_list_tools(msg: Message):
            if msg.data.get("action") == "list_tools":
                response = Message(
                    type="tools_list_response",
                    source=f"{self.adapter_name}Adapter",
                    data={
                        "adapter_name": self.adapter_name,
                        "tools": [tool.to_dict() for tool in self._tools_cache]
                    }
                )
                await self.response_channel.publish(response)

        @self.agent.subscribe(self.call_channel)
        async def handle_call_tool(msg: Message):
            if msg.data.get("action") == "call_tool":
                tool_name = msg.data.get("name")
                parameters = msg.data.get("parameters", {})
                call_id = msg.data.get("call_id")
                
                try:
                    result = await self.execute_tool(tool_name, parameters)
                    request_timestamp = msg.data.get("timestamp")
                    response = Message(
                        type="tool_call_response",
                        source=f"{self.adapter_name}Adapter", 
                        data={
                            "call_id": call_id,
                            "tool_name": tool_name,
                            "result": result.to_dict(),
                            "timestamp": request_timestamp
                        }
                    )
                except Exception as e:
                    request_timestamp = msg.data.get("timestamp")
                    response = Message(
                        type="tool_call_response",
                        source=f"{self.adapter_name}Adapter",
                        data={
                            "call_id": call_id,
                            "tool_name": tool_name,
                            "result": ToolResult(False, None, str(e)).to_dict(),
                            "timestamp": request_timestamp
                        }
                    )
                
                await self.call_response_channel.publish(response)

        await self.agent.start()
        self._initialized = True

    async def stop(self):
        """Stop the adapter service."""
        if self._initialized:
            await self.cleanup_backend()
            await self.agent.stop()
            self._initialized = False


def run_adapter(adapter: BaseAdapter):
    """Helper function to run an adapter as a standalone process."""
    eggai_set_default_transport(lambda: KafkaTransport())
    
    async def main():
        try:
            await adapter.start()
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            pass
        except Exception as e:
            raise
        finally:
            try:
                await adapter.stop()
            except Exception:
                pass

    asyncio.run(main())