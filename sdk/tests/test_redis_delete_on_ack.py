"""
delete_on_ack: acked stream entries are XDEL'd, so consumed messages stop
occupying Redis memory. Integration tests against a real Redis at localhost:6379.
"""

import asyncio
import uuid

import pytest
import pytest_asyncio
import redis.asyncio as redis
from faststream import AckPolicy

from eggai import Agent, Channel
from eggai.transport import RedisTransport


async def _wait_for(predicate, timeout=10.0, interval=0.1):
    deadline = asyncio.get_running_loop().time() + timeout
    while True:
        if await predicate():
            return
        if asyncio.get_running_loop().time() > deadline:
            raise AssertionError("condition not met before timeout")
        await asyncio.sleep(interval)


def _pending(info):
    return info.get("pending", 0) if isinstance(info, dict) else info[0]


@pytest_asyncio.fixture
async def redis_client():
    client = redis.Redis(host="localhost", port=6379, decode_responses=True)
    yield client
    await client.aclose()


def _names(prefix):
    test_id = uuid.uuid4().hex[:8]
    agent_name = f"{prefix}-{test_id}"
    channel_name = f"{prefix}-ch-{test_id}"
    return agent_name, channel_name, f"eggai.{channel_name}"


@pytest.mark.asyncio
async def test_delete_on_ack_removes_handled_entries(redis_client):
    agent_name, channel_name, stream = _names("doa-ok")
    transport = RedisTransport()
    agent = Agent(agent_name, transport=transport)
    channel = Channel(channel_name, transport=transport)
    group = f"{agent_name}-handler-1"

    seen = []

    @agent.subscribe(channel=channel, delete_on_ack=True)
    async def handler(message):
        seen.append(message["n"])

    await agent.start()
    try:
        for n in range(5):
            await channel.publish({"type": "t", "n": n})
        await _wait_for(lambda: _async(len(seen) == 5))
        await _wait_for(lambda: _xlen_is(redis_client, stream, 0))
        assert _pending(await redis_client.xpending(stream, group)) == 0
    finally:
        await agent.stop()
    assert sorted(seen) == [0, 1, 2, 3, 4]


@pytest.mark.asyncio
async def test_without_delete_on_ack_entries_stay(redis_client):
    """Contrast: default behaviour keeps acked entries in the stream."""
    agent_name, channel_name, stream = _names("doa-off")
    transport = RedisTransport()
    agent = Agent(agent_name, transport=transport)
    channel = Channel(channel_name, transport=transport)

    seen = []

    @agent.subscribe(channel=channel)
    async def handler(message):
        seen.append(message["n"])

    await agent.start()
    try:
        for n in range(3):
            await channel.publish({"type": "t", "n": n})
        await _wait_for(lambda: _async(len(seen) == 3))
        await asyncio.sleep(0.3)
        assert await redis_client.xlen(stream) == 3
    finally:
        await agent.stop()


@pytest.mark.asyncio
async def test_delete_on_ack_keeps_failed_entry_in_pel(redis_client):
    agent_name, channel_name, stream = _names("doa-fail")
    transport = RedisTransport()
    agent = Agent(agent_name, transport=transport)
    channel = Channel(channel_name, transport=transport)
    group = f"{agent_name}-handler-1"

    called = asyncio.Event()

    @agent.subscribe(channel=channel, delete_on_ack=True)
    async def handler(message):
        called.set()
        raise RuntimeError("boom")

    await agent.start()
    try:
        await channel.publish({"type": "t"})
        await asyncio.wait_for(called.wait(), timeout=10.0)
        await asyncio.sleep(0.3)
        assert await redis_client.xlen(stream) == 1
        assert _pending(await redis_client.xpending(stream, group)) == 1
    finally:
        await agent.stop()


@pytest.mark.asyncio
async def test_delete_on_ack_deletes_filtered_out_entries(redis_client):
    agent_name, channel_name, stream = _names("doa-filter")
    transport = RedisTransport()
    agent = Agent(agent_name, transport=transport)
    channel = Channel(channel_name, transport=transport)

    seen = []

    @agent.subscribe(
        channel=channel,
        delete_on_ack=True,
        filter_by_message=lambda m: m.get("keep"),
    )
    async def handler(message):
        seen.append(message["n"])

    await agent.start()
    try:
        await channel.publish({"type": "t", "n": 1, "keep": False})
        await channel.publish({"type": "t", "n": 2, "keep": True})
        await _wait_for(lambda: _async(seen == [2]))
        await _wait_for(lambda: _xlen_is(redis_client, stream, 0))
    finally:
        await agent.stop()


@pytest.mark.asyncio
async def test_delete_on_ack_through_retry_stream(redis_client):
    """Fail once, succeed on retry: main and retry streams both end empty."""
    agent_name, channel_name, stream = _names("doa-retry")
    group = f"{agent_name}-handler-1"
    retry_stream = f"{stream}.{group}.retry"
    transport = RedisTransport()
    agent = Agent(agent_name, transport=transport)
    channel = Channel(channel_name, transport=transport)

    calls = 0
    done = asyncio.Event()

    @agent.subscribe(
        channel=channel,
        delete_on_ack=True,
        retry_on_idle_ms=300,
        retry_reclaim_interval_s=0.5,
    )
    async def handler(message):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("transient")
        done.set()

    await agent.start()
    try:
        await channel.publish({"type": "t"})
        await asyncio.wait_for(done.wait(), timeout=10.0)
        await _wait_for(lambda: _xlen_is(redis_client, stream, 0))
        await _wait_for(lambda: _xlen_is(redis_client, retry_stream, 0))
    finally:
        await agent.stop()
    assert calls == 2


@pytest.mark.asyncio
async def test_delete_on_ack_through_dlq(redis_client):
    """Always failing: main and retry streams end empty, the DLQ keeps the entry."""
    agent_name, channel_name, stream = _names("doa-dlq")
    group = f"{agent_name}-handler-1"
    retry_stream = f"{stream}.{group}.retry"
    dlq_stream = f"{stream}.{group}.dlq"
    transport = RedisTransport()
    agent = Agent(agent_name, transport=transport)
    channel = Channel(channel_name, transport=transport)

    @agent.subscribe(
        channel=channel,
        delete_on_ack=True,
        retry_on_idle_ms=300,
        retry_reclaim_interval_s=0.5,
        max_retries=1,
    )
    async def handler(message):
        raise RuntimeError("permanent")

    await agent.start()
    try:
        await channel.publish({"type": "t"})
        await _wait_for(lambda: _xlen_is(redis_client, dlq_stream, 1), timeout=15.0)
        await _wait_for(lambda: _xlen_is(redis_client, stream, 0))
        await _wait_for(lambda: _xlen_is(redis_client, retry_stream, 0))
    finally:
        await agent.stop()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "extra, match",
    [
        ({"no_ack": True}, "no_ack"),
        ({"ack_policy": AckPolicy.MANUAL}, "MANUAL"),
    ],
)
async def test_delete_on_ack_rejects_incompatible_options(extra, match):
    transport = RedisTransport()

    async def handler(message):
        pass

    with pytest.raises(ValueError, match=match):
        await transport.subscribe(
            "doa-invalid", handler, handler_id="h", delete_on_ack=True, **extra
        )


@pytest.mark.asyncio
async def test_delete_on_ack_requires_group():
    transport = RedisTransport()

    async def handler(message):
        pass

    with pytest.raises(ValueError, match="consumer group"):
        await transport.subscribe("doa-nogroup", handler, delete_on_ack=True)


async def _async(value):
    return value


async def _xlen_is(client, stream, n):
    return await client.xlen(stream) == n
