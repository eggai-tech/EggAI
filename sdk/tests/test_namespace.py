from contextlib import contextmanager

import pytest

import eggai.channel
from eggai import Channel


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
