"""Unit tests for Agent subscription wiring.

Broker-independent: the subscribe decorator runs synchronously at decoration time,
so these need no Redis/Kafka service.
"""

import pytest

from eggai import Agent, Channel


def test_plugin_kwargs_without_initialized_plugin_raises():
    """Passing plugin-prefixed kwargs (e.g. ``a2a_*``) to subscribe() without
    initializing that plugin via the Agent(...) constructor must raise a clear
    error rather than an opaque KeyError on self.plugins."""
    agent = Agent("test-agent")  # no a2a config -> a2a plugin not initialized

    with pytest.raises(ValueError, match="'a2a' plugin is not initialized"):

        @agent.subscribe(channel=Channel("test"), a2a_skill="greet")
        async def handler(message):
            return message
