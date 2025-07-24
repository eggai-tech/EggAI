import asyncio
from typing import List

import fastmcp.tools
from eggai import eggai_main, Agent, Channel
from fastmcp import Client

from eggai_adapter.types import ToolListRequestMessage, ExternalTool, ToolListResponseMessage, ToolListResponse, \
    ToolCallRequestMessage, ToolCallResponseMessage, ToolCallResponse


@eggai_main
async def run_mcp_adapter(name: str, mcp_sse_url: str):
    agent = Agent(name)

    def c(suffix: str) -> Channel:
        return Channel(f"tools.{name}.{suffix}")

    @agent.subscribe(
        channel=c("list.in"),
        auto_offset_reset="latest",
        group_id=name+"_tools_list_in",
    )
    async def handle_tool_list_request(message: ToolListRequestMessage):
        if message.data.adapter_name != name:
            return
        client = Client(mcp_sse_url)
        async with client:
            mcp_tools: List[fastmcp.tools.Tool] = await client.list_tools()
            tools: List[ExternalTool] = []
            for tool in mcp_tools:
                external_tool = ExternalTool(
                    name=tool.name,
                    description=tool.description or tool.annotations.title,
                    parameters=tool.inputSchema if hasattr(tool, 'inputSchema') else {},
                    return_type=tool.outputSchema if hasattr(tool, 'outputSchema') else {}
                )
                tools.append(external_tool)
            response = ToolListResponseMessage(
                source=name,
                data=ToolListResponse(
                    call_id=message.data.call_id,
                    tools=tools
                )
            )
            await c("list.out").publish(response)

    @agent.subscribe(
        channel=c("calls.in"),
        auto_offset_reset="latest",
        group_id=name+"_tool_calls_in",
    )
    async def handle_tool_call_request(message: ToolCallRequestMessage):
        if message.data.tool_name is None or message.data.call_id is None:
            return
        client = Client(mcp_sse_url)
        async with client:
            try:
                result = await client.call_tool(message.data.tool_name, message.data.parameters)
                response = ToolCallResponseMessage(
                    source=name,
                    data=ToolCallResponse(
                        call_id=message.data.call_id,
                        tool_name=message.data.tool_name,
                        data=result.data,
                        is_error=result.is_error
                    )
                )
            except Exception as e:
                response = ToolCallResponseMessage(
                    source=name,
                    data=ToolCallResponse(
                        call_id=message.data.call_id,
                        tool_name=message.data.tool_name,
                        data=str(e),
                        is_error=True
                    )
                )
            await c("calls.out").publish(response)

    await agent.start()

    try:
        await asyncio.Future()
    except (KeyboardInterrupt, asyncio.CancelledError):
        pass
