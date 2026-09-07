import asyncio
from contextlib import contextmanager

import pytest

import eggai.channel
from eggai import Agent, Channel
from eggai.transport import InMemoryTransport, eggai_set_default_transport


class TestNamespace:
    """Test namespace functionality in Channel class."""

    @contextmanager
    def _override_namespace(self, namespace):
        """Context manager to temporarily override the global NAMESPACE."""
        original = eggai.channel.NAMESPACE
        try:
            eggai.channel.NAMESPACE = namespace
            yield
        finally:
            eggai.channel.NAMESPACE = original

    @pytest.mark.parametrize(
        "namespace,channel_name,expected",
        [
            (eggai.channel.NAMESPACE, None, "eggai.channel"),
            ("dev", "events", "dev.events"),
            ("test", "logs", "test.logs"),
            ("prod", None, "prod.channel"),
            ("staging", "", "staging.channel"),
        ],
    )
    def test_namespace_combinations(self, namespace, channel_name, expected):
        """Test various namespace and channel name combinations."""
        with self._override_namespace(namespace):
            channel = Channel(name=channel_name)
            assert channel._name == expected

    @pytest.mark.asyncio
    async def test_agent_subscribe_default_channel_uses_namespace(self):
        """Bare @agent.subscribe() and bare Channel() must resolve to the same name."""
        eggai_set_default_transport(lambda: InMemoryTransport())
        received = []
        with self._override_namespace("custom"):
            agent = Agent("namespace-agent")

            @agent.subscribe()
            async def handler(msg):
                received.append(msg)

            await agent.start()
            await Channel().publish({"type": "ping"})
            await asyncio.sleep(0.1)
            await agent.stop()

        assert agent._subscriptions[0][0] == "custom.channel"
        assert len(received) == 1
