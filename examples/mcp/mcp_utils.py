import asyncio
import uuid
from typing import List, Dict, Any

from eggai import Agent, Channel
from mcp import Tool, InitializeResult, ClientSession, StdioServerParameters, stdio_client
from mcp.client.sse import sse_client

async def mcp_sse_to_eggai(
        agent_name: str,
        sse_url: str = None,
        stdio_server_params: StdioServerParameters = None
):
    def mcp_client():
        if stdio_server_params:
            return stdio_client(stdio_server_params)
        if sse_url:
            return sse_client(sse_url)
        raise ValueError("Either sse_url or server_params must be provided")

    async with mcp_client() as streams:
        async with ClientSession(streams[0], streams[1]) as session:
            tools: List[Tool]
            init_result: InitializeResult
            channel_in = Channel(f"eggai.mcp.{agent_name}.in")
            channel_out = Channel(f"eggai.mcp.{agent_name}.out")
            agent = Agent(agent_name)
            init_result = await session.initialize()
            list_res = await session.list_tools()
            tools = list_res.tools

            print(f"{agent_name} bound with mcp server {init_result.serverInfo.name}")

            @agent.subscribe(channel_in, filter_by_message=lambda msg: msg.get("type") == "call_tool")
            async def call_tool(msg):
                try:
                    tool_name = msg.get("tool")
                    tool_args = msg.get("arguments", None)
                    res = await session.call_tool(tool_name, arguments=tool_args)
                    await channel_out.publish({
                        "id": uuid.uuid4().hex,
                        "correlation_id": msg.get("id"),
                        "type": "tool_result",
                        "agent": agent_name,
                        "result": res
                    })
                except Exception as e:
                    print(f"Error calling tool: {e}")
                    await channel_out.publish({
                        "id": uuid.uuid4().hex,
                        "correlation_id": msg.get("id"),
                        "type": "tool_result",
                        "agent": agent_name,
                        "result": {"content": "Error calling tool"}
                    })

            @agent.subscribe(channel_in, filter_by_message=lambda msg: msg.get("type") == "list_tools")
            async def list_tools(msg):
                try:
                    await channel_out.publish({
                        "id": uuid.uuid4().hex,
                        "correlation_id": msg.get("id"),
                        "type": "tools_list",
                        "agent": agent_name,
                        "tools": tools
                    })
                except Exception as e:
                    print(f"Error listing tools: {e}")
                    await channel_out.publish({
                        "id": uuid.uuid4().hex,
                        "correlation_id": msg.get("id"),
                        "type": "tools_list",
                        "agent": agent_name,
                        "tools": []
                    })

            await agent.start()
            await asyncio.Future()


class EggaiMcpAgent:
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
