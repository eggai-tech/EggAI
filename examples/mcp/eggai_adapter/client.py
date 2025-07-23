import asyncio
import uuid
from typing import Dict, Any, Optional, List

from eggai import Agent, Channel

from eggai_adapter.types import ExternalTool, ToolListRequest, ToolListRequestMessage, ToolListResponseMessage, \
    ToolCallRequest, ToolCallRequestMessage, ToolCallResponse, ToolCallResponseMessage


class EggaiAdapterClient:
    def __init__(self, adapter: str):
        self.adapter = adapter
        self.futures: Dict[uuid.UUID, Dict[str, Any]] = {}
        self.source = "EggaiAdapterClient" + adapter
        self.tool_agent = Agent(self.source)
        self.running_task = asyncio.create_task(self.start())

    def c(self, suffix: str) -> Channel:
        return Channel(f"tools.{self.adapter}.{suffix}")

    async def start(self):
        @self.tool_agent.subscribe(channel=self.c("calls.out"))
        async def handle_tool_call_response(msg: ToolCallResponseMessage):
            call_id = msg.data.call_id
            if call_id in self.futures:
                future = self.futures[call_id]
                future["result"] = msg.data
                future["result_event"].set()

        @self.tool_agent.subscribe(channel=self.c("list.out"))
        async def handle_tool_list_response(msg: ToolListResponseMessage):
            call_id = msg.data.call_id
            if call_id in self.futures:
                future = self.futures[call_id]
                future["result"] = msg.data.tools
                future["result_event"].set()

        await self.tool_agent.start()

    async def call_tool(self, tool_name: str, parameters: Optional[Dict[str, Any]] = None) -> ToolCallResponse:
        call_uuid = uuid.uuid4()
        self.futures[call_uuid] = {
            "result_event": asyncio.Event(),
            "result": None
        }
        await self.c("calls.in").publish(
            ToolCallRequestMessage(
                source=self.source,
                data=ToolCallRequest(
                    call_id=call_uuid,
                    tool_name=tool_name,
                    parameters=parameters
                )
            )
        )
        await self.futures[call_uuid]["result_event"].wait()
        result = self.futures[call_uuid]["result"]
        del self.futures[call_uuid]
        return result

    async def retrieve_tools(self) -> List[ExternalTool]:
        call_uuid = uuid.uuid4()
        self.futures[call_uuid] = {
            "result_event": asyncio.Event(),
            "result": None
        }

        await self.c("list.in").publish(
            ToolListRequestMessage(
                source=self.source,
                data=ToolListRequest(
                    call_id=call_uuid,
                    adapter_name=self.adapter
                )
            )
        )

        await self.futures[call_uuid]["result_event"].wait()
        discovered_tools: List[ExternalTool] = self.futures[call_uuid]["result"]
        del self.futures[call_uuid]
        return discovered_tools
