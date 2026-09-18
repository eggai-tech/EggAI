import asyncio
import uuid

import pytest

from eggai import Agent, Channel
from eggai.transport import InMemoryTransport, eggai_set_default_transport

pytest.importorskip("fastmcp")

from fastmcp import FastMCP  # noqa: E402

from eggai.adapters.mcp.mcp import run_mcp_adapter  # noqa: E402
from eggai.adapters.mcp.models import (  # noqa: E402
    ToolCallRequest,
    ToolCallRequestMessage,
    ToolCallResponseMessage,
    ToolListRequest,
    ToolListRequestMessage,
    ToolListResponseMessage,
)


@pytest.mark.asyncio
async def test_mcp_adapter_lists_and_calls_tools():
    eggai_set_default_transport(lambda: InMemoryTransport())

    server = FastMCP("calc")

    @server.tool
    def add(a: int, b: int) -> int:
        """Add two integers."""
        return a + b

    name = f"calc-{uuid.uuid4().hex[:8]}"
    list_responses: list[ToolListResponseMessage] = []
    call_responses: list[ToolCallResponseMessage] = []

    client = Agent(f"{name}-client")

    @client.subscribe(
        channel=Channel(f"tools.{name}.list.out"), data_type=ToolListResponseMessage
    )
    async def on_list(message: ToolListResponseMessage):
        list_responses.append(message)

    @client.subscribe(
        channel=Channel(f"tools.{name}.calls.out"), data_type=ToolCallResponseMessage
    )
    async def on_call(message: ToolCallResponseMessage):
        call_responses.append(message)

    await client.start()
    adapter = asyncio.create_task(run_mcp_adapter(name, server))
    await asyncio.sleep(0.2)

    list_id = uuid.uuid4()
    await Channel(f"tools.{name}.list.in").publish(
        ToolListRequestMessage(
            source="test",
            data=ToolListRequest(call_id=list_id, adapter_name=name),
        )
    )
    ok_id = uuid.uuid4()
    await Channel(f"tools.{name}.calls.in").publish(
        ToolCallRequestMessage(
            source="test",
            data=ToolCallRequest(
                call_id=ok_id, tool_name="add", parameters={"a": 2, "b": 3}
            ),
        )
    )
    bad_id = uuid.uuid4()
    await Channel(f"tools.{name}.calls.in").publish(
        ToolCallRequestMessage(
            source="test",
            data=ToolCallRequest(call_id=bad_id, tool_name="missing", parameters={}),
        )
    )
    await asyncio.sleep(0.5)

    adapter.cancel()
    await adapter
    await client.stop()

    assert len(list_responses) == 1
    listed = list_responses[0].data
    assert listed.call_id == list_id
    assert [t.name for t in listed.tools] == ["add"]
    tool = listed.tools[0]
    assert tool.description == "Add two integers."
    assert tool.parameters["properties"] == {
        "a": {"type": "integer"},
        "b": {"type": "integer"},
    }
    assert tool.parameters["required"] == ["a", "b"]
    assert tool.return_type["properties"] == {"result": {"type": "integer"}}

    by_id = {r.data.call_id: r.data for r in call_responses}
    assert set(by_id) == {ok_id, bad_id}
    assert by_id[ok_id].is_error is False
    assert by_id[ok_id].data["structured_content"] == {"result": 5}
    assert by_id[bad_id].is_error is True
    assert "missing" in by_id[bad_id].data
