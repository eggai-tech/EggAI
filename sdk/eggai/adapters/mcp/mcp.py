import asyncio
from typing import List

from eggai import eggai_main, Agent, Channel
from eggai.adapters.mcp.models import (
    ToolListRequestMessage,
    ExternalTool,
    ToolListResponseMessage,
    ToolListResponse,
    ToolCallRequestMessage,
    ToolCallResponseMessage,
    ToolCallResponse,
)

try:
    from fastmcp import FastMCP
except ImportError:
    raise ImportError(
        "MCP functionality requires the mcp extra. Install with: pip install eggai[mcp]"
    )


@eggai_main
async def run_mcp_adapter(name: str, mcp_server: FastMCP):
    """Run MCP adapter with a FastMCP server instance."""
    agent = Agent(name)

    def c(suffix: str) -> Channel:
        return Channel(f"tools.{name}.{suffix}")

    @agent.subscribe(
        channel=c("list.in"),
        auto_offset_reset="latest",
        group_id=name + "_tools_list_in",
    )
    async def handle_tool_list_request(message: ToolListRequestMessage):
        if message.data.adapter_name != name:
            return

        mcp_tools = await mcp_server.list_tools()
        tools: List[ExternalTool] = []
        for tool in mcp_tools:
            external_tool = ExternalTool(
                name=tool.name,
                description=tool.description,
                parameters=getattr(tool, "inputSchema", {}),
                return_type=getattr(tool, "outputSchema", {}),
            )
            tools.append(external_tool)

        response = ToolListResponseMessage(
            source=name,
            data=ToolListResponse(call_id=message.data.call_id, tools=tools),
        )
        await c("list.out").publish(response)

    @agent.subscribe(
        channel=c("calls.in"),
        auto_offset_reset="latest",
        group_id=name + "_tool_calls_in",
    )
    async def handle_tool_call_request(message: ToolCallRequestMessage):
        if message.data.tool_name is None or message.data.call_id is None:
            return

        try:
            result = await mcp_server.call_tool(
                message.data.tool_name, message.data.parameters
            )
            response = ToolCallResponseMessage(
                source=name,
                data=ToolCallResponse(
                    call_id=message.data.call_id,
                    tool_name=message.data.tool_name,
                    data=result,
                    is_error=False,
                ),
            )
        except Exception as e:
            response = ToolCallResponseMessage(
                source=name,
                data=ToolCallResponse(
                    call_id=message.data.call_id,
                    tool_name=message.data.tool_name,
                    data=str(e),
                    is_error=True,
                ),
            )
        await c("calls.out").publish(response)

    await agent.start()

    try:
        await asyncio.Future()
    except (KeyboardInterrupt, asyncio.CancelledError):
        pass
