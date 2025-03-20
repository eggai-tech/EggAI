from eggai import Channel


import asyncio
import uuid
from typing import Any, Dict


class EggaiMcpAdapterClient:
    def __init__(self, name: str):
        self.name = name
        self._initialized = False
        self.channel_in = Channel(f"eggai.mcp.{name}.in")
        self.channel_out = Channel(f"eggai.mcp.{name}.out")
        self.pending_requests = {}

    async def _initialize(self):
        if not self._initialized:
            await self.channel_out.subscribe(self._handle_mcp_output)
            self._initialized = True

    async def _handle_mcp_output(self, msg: Dict[str, Any]):
        message_type = msg.get("type")
        correlation_id = msg.get("correlation_id")

        if message_type == "tools_list":
            if correlation_id in self.pending_requests:
                tools = msg.get("tools", [])
                future = self.pending_requests.pop(correlation_id)
                if future:
                    future.set_result(tools)
        elif message_type == "tool_result":
            if correlation_id in self.pending_requests:
                result = msg.get("result")
                future = self.pending_requests.pop(correlation_id)
                if future:
                    future.set_result(result)
        else:
            pass

    async def list_tools(self):
        await self._initialize()
        correlation_id = uuid.uuid4().hex
        future = asyncio.get_event_loop().create_future()
        self.pending_requests[correlation_id] = future

        await self.channel_in.publish({
            "id": correlation_id,
            "type": "list_tools"
        })

        tools = await future
        return tools

    async def call_tool(self, tool_name: str, arguments: dict):
        await self._initialize()
        correlation_id = uuid.uuid4().hex
        future = asyncio.get_event_loop().create_future()
        self.pending_requests[correlation_id] = future

        await self.channel_in.publish({
            "id": correlation_id,
            "type": "call_tool",
            "tool": tool_name,
            "arguments": arguments
        })

        result = await future
        return result