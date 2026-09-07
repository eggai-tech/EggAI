import httpx
import pytest
from uuid import uuid4

from google.protobuf.json_format import ParseDict
from google.protobuf.struct_pb2 import Value
from starlette.applications import Starlette

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.routes import create_jsonrpc_routes
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import Message, Part, Role

from eggai import Agent, Channel
from eggai.adapters.a2a.config import A2AConfig
from eggai.adapters.a2a.plugin import A2APlugin


def test_a2a_agent_card_uses_1x_interface():
    plugin = A2APlugin()
    plugin.config = A2AConfig(
        agent_name="test-agent",
        description="Test A2A agent",
        version="1.0.0",
        base_url="http://localhost:8080",
    )

    card = plugin.create_agent_card()

    assert card.name == "test-agent"
    assert card.description == "Test A2A agent"
    assert card.version == "1.0.0"
    assert len(card.supported_interfaces) == 1
    assert card.supported_interfaces[0].url == "http://localhost:8080"
    assert card.supported_interfaces[0].protocol_binding == "JSONRPC"
    assert card.supported_interfaces[0].protocol_version == "1.0"


def test_a2a_agent_card_registers_skill():
    plugin = A2APlugin()
    plugin.config = A2AConfig(
        agent_name="test-agent",
        description="Test A2A agent",
    )

    async def handler(message):
        return {"ok": True}

    plugin.register_skill("test-skill", handler, None)

    card = plugin.create_agent_card()

    assert len(card.skills) == 1
    assert card.skills[0].id == "test-skill"


class EggAITestExecutor(AgentExecutor):
    def __init__(self, plugin):
        self.plugin = plugin

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        result = await self.plugin.handlers["test-skill"](context.message)
        await event_queue.enqueue_event(
            Message(
                message_id=str(uuid4()),
                role=Role.ROLE_AGENT,
                parts=[Part(data=ParseDict(result, Value()))],
            )
        )

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        pass


@pytest.mark.asyncio
async def test_a2a_skill_round_trip():
    plugin = A2APlugin()
    plugin.config = A2AConfig(
        agent_name="test-agent",
        description="Test A2A agent",
        version="1.0.0",
        base_url="http://testserver",
    )

    async def handler(message):
        return {"result": "hello"}

    plugin.register_skill("test-skill", handler, None)

    agent_card = plugin.create_agent_card()

    request_handler = DefaultRequestHandler(
        agent_executor=EggAITestExecutor(plugin),
        task_store=InMemoryTaskStore(),
        agent_card=agent_card,
    )

    routes = create_jsonrpc_routes(
        request_handler=request_handler,
        rpc_url="/",
    )

    app = Starlette(routes=routes)

    request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "SendMessage",
        "params": {
            "message": {
                "messageId": "test-message-id",
                "role": "ROLE_USER",
                "parts": [{"text": "test-skill"}],
            }
        },
    }

    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as client:
        response = await client.post(
            "/",
            json=request,
            headers={"A2A-Version": "1.0"},
        )

    assert response.status_code == 200

    body = response.json()

    assert body["jsonrpc"] == "2.0"
    assert "error" not in body
    assert "result" in body


def test_plugin_kwargs_without_initialized_plugin_raises():
    """Passing plugin-prefixed kwargs (e.g. ``a2a_*``) to subscribe() without
    initializing that plugin via the Agent(...) constructor must raise a clear
    error rather than an opaque KeyError on self.plugins."""
    agent = Agent("test-agent")  # no a2a config -> a2a plugin not initialized

    with pytest.raises(ValueError, match="'a2a' plugin is not initialized"):

        @agent.subscribe(channel=Channel("test"), a2a_skill="greet")
        async def handler(message):
            return message

    # The guard runs before the subscription is registered, so a rejected
    # subscription must not leave a half-registered handler behind.
    assert agent._subscriptions == []