"""The brokers are extras: the core works without them, a transport names its extra.

conftest skips a test whose id names a broker, or whose source names the Kafka
transport, when that broker is not running; these tests need no broker, so the
names live in the constants below.
"""

import importlib
import subprocess
import sys
import textwrap

import pytest

import eggai
import eggai.transport

BROKER_PACKAGES = ("faststream", "redis", "aiokafka")
# Transport -> (its module, its extra, the broker client only it needs).
TRANSPORTS = {
    "KafkaTransport": ("eggai.transport.kafka", "kafka", "aiokafka"),
    "RedisTransport": ("eggai.transport.redis", "redis", "redis"),
}


def _run(code: str, *, blocked: tuple[str, ...]) -> subprocess.CompletedProcess:
    """Run ``code`` in a fresh interpreter that cannot import ``blocked``."""
    prelude = "import sys\n" + "".join(f"sys.modules[{p!r}] = None\n" for p in blocked)
    return subprocess.run(
        [sys.executable, "-c", prelude + textwrap.dedent(code)],
        capture_output=True,
        text=True,
        timeout=60,
    )


def test_the_core_runs_without_any_broker_installed():
    result = _run(
        """
        import asyncio

        from eggai import Agent, Channel, InMemoryTransport
        from eggai.transport import (
            LeaseLostError,
            ProcessingTimeoutError,
            eggai_set_default_transport,
        )

        eggai_set_default_transport(InMemoryTransport)
        received = []


        async def main():
            agent = Agent("agent")
            channel = Channel("channel")

            @agent.subscribe(channel=channel)
            async def handle(event):
                received.append(event["type"])

            await agent.start()
            await channel.publish({"type": "ping"})
            await asyncio.sleep(0.1)
            await agent.stop()


        asyncio.run(main())
        assert received == ["ping"], received
        """,
        blocked=BROKER_PACKAGES,
    )
    assert result.returncode == 0, result.stderr


def test_each_broker_transport_names_its_missing_extra():
    cases = [
        (name, extra, blocked)
        for name, (_, extra, client) in TRANSPORTS.items()
        for blocked in [(client,), ("faststream",)]
    ]
    for name, extra, blocked in cases:
        for module in ("eggai", "eggai.transport"):
            result = _run(
                f"""
                try:
                    from {module} import {name}
                except ImportError as e:
                    assert type(e) is ImportError, type(e)
                    print(e)
                else:
                    raise SystemExit("imported without its extra")
                """,
                blocked=blocked,
            )
            assert result.returncode == 0, (name, blocked, module, result.stderr)
            assert (
                result.stdout.strip()
                == f"{name} needs the {extra!r} extra: pip install 'eggai[{extra}]'"
            )


def test_one_broker_installed_is_enough_for_its_transport():
    for name, (_, _, client) in TRANSPORTS.items():
        others = tuple(c for _, _, c in TRANSPORTS.values() if c != client)
        result = _run(f"from eggai import {name}", blocked=others)
        assert result.returncode == 0, (name, others, result.stderr)


def test_a_missing_module_of_the_sdk_itself_is_not_taken_for_an_extra():
    name, (module, _, _) = next(iter(TRANSPORTS.items()))
    result = _run(f"from eggai.transport import {name}", blocked=(module,))
    assert result.returncode != 0
    assert "ModuleNotFoundError" in result.stderr
    assert "extra" not in result.stderr


def test_the_transports_resolve_to_their_classes_on_first_use():
    for name, (module, _, _) in TRANSPORTS.items():
        transport = getattr(importlib.import_module(module), name)
        assert getattr(eggai, name) is getattr(eggai.transport, name) is transport
        assert name in dir(eggai) and name in dir(eggai.transport)
    with pytest.raises(AttributeError, match="no attribute 'NoSuchTransport'"):
        _ = eggai.transport.NoSuchTransport
    with pytest.raises(AttributeError, match="no attribute 'NoSuchTransport'"):
        _ = eggai.NoSuchTransport
