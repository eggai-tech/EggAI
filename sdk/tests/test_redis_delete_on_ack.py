"""
delete_on_ack: acked stream entries are XDEL'd, so consumed messages stop
occupying Redis memory. Integration tests against a real Redis at localhost:6379.
"""

import asyncio
import logging
import threading
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
        assert transport._delete_client is not None  # opened by connect()
        for n in range(5):
            await channel.publish({"type": "t", "n": n})
        await _wait_for(lambda: _async(len(seen) == 5))
        await _wait_for(lambda: _xlen_is(redis_client, stream, 0))
        assert _pending(await redis_client.xpending(stream, group)) == 0
        # Only delivered entries are deleted, so Redis can still compute the
        # group's lag (null means it can't); KEDA's lagCount scaler reads it.
        (info,) = [
            g for g in await redis_client.xinfo_groups(stream) if g["name"] == group
        ]
        assert info["lag"] == 0
    finally:
        await agent.stop()
    assert sorted(seen) == [0, 1, 2, 3, 4]
    assert transport._delete_client is None  # closed by disconnect()


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
    assert transport._delete_client is None  # no delete_on_ack, no extra client
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
async def test_delete_on_ack_with_ack_policy_ack_deletes_failures(redis_client):
    """AckPolicy.ACK acks a failed run too, so delete_on_ack must delete it too."""
    agent_name, channel_name, stream = _names("doa-ackpol")
    transport = RedisTransport()
    agent = Agent(agent_name, transport=transport)
    channel = Channel(channel_name, transport=transport)
    group = f"{agent_name}-handler-1"

    called = asyncio.Event()

    @agent.subscribe(channel=channel, delete_on_ack=True, ack_policy=AckPolicy.ACK)
    async def handler(message):
        called.set()
        raise RuntimeError("boom")

    await agent.start()
    try:
        await channel.publish({"type": "t"})
        await asyncio.wait_for(called.wait(), timeout=10.0)
        await _wait_for(lambda: _xlen_is(redis_client, stream, 0))
        assert _pending(await redis_client.xpending(stream, group)) == 0
    finally:
        await agent.stop()


@pytest.mark.asyncio
async def test_delete_on_ack_runs_sync_handler_off_the_event_loop(redis_client):
    agent_name, channel_name, stream = _names("doa-sync")
    transport = RedisTransport()
    agent = Agent(agent_name, transport=transport)
    channel = Channel(channel_name, transport=transport)

    loop_thread = threading.get_ident()
    handler_threads = []

    @agent.subscribe(channel=channel, delete_on_ack=True)
    def handler(message):
        handler_threads.append(threading.get_ident())

    await agent.start()
    try:
        await channel.publish({"type": "t"})
        await _wait_for(lambda: _async(len(handler_threads) == 1))
        await _wait_for(lambda: _xlen_is(redis_client, stream, 0))
    finally:
        await agent.stop()
    assert handler_threads[0] != loop_thread


@pytest.mark.asyncio
async def test_delete_on_ack_keeps_poison_entry_when_no_dlq(redis_client):
    """With no DLQ a dropped poison entry is the only copy: ack it, don't XDEL it."""
    agent_name, channel_name, stream = _names("doa-poison")
    group = f"{agent_name}-handler-1"
    transport = RedisTransport()
    agent = Agent(agent_name, transport=transport)
    channel = Channel(channel_name, transport=transport)

    @agent.subscribe(
        channel=channel,
        delete_on_ack=True,
        retry_on_idle_ms=300,
        retry_reclaim_interval_s=0.5,
        max_retries=None,
    )
    async def handler(message):
        raise RuntimeError("never succeeds")

    await agent.start()
    try:
        # No __data__ field: the reclaimer cannot parse it (poison).
        await redis_client.xadd(stream, {"garbage": "x"})

        async def acked():
            return _pending(await redis_client.xpending(stream, group)) == 0 and (
                await redis_client.xlen(stream) == 1
            )

        await asyncio.sleep(0.5)
        await _wait_for(acked, timeout=15.0)
    finally:
        await agent.stop()


@pytest.mark.asyncio
async def test_delete_on_ack_refuses_to_start_next_to_another_group(redis_client):
    """Another group on the stream (e.g. a monitoring bridge) would miss deleted
    entries: connect() must fail before anything is consumed."""
    agent_name, channel_name, stream = _names("doa-foreign")
    await redis_client.xgroup_create(stream, "someone-else", id="$", mkstream=True)
    await redis_client.xadd(stream, {"k": "v"})

    transport = RedisTransport()
    agent = Agent(agent_name, transport=transport)
    channel = Channel(channel_name, transport=transport)
    calls = []

    @agent.subscribe(channel=channel, delete_on_ack=True)
    async def handler(message):
        calls.append(message)

    with pytest.raises(RuntimeError, match="someone-else"):
        await agent.start()
    assert transport._delete_client is None  # not leaked by the failed connect()
    await transport.disconnect()
    assert calls == []
    assert await redis_client.xlen(stream) == 1


@pytest.mark.asyncio
async def test_delete_on_ack_refuses_two_local_groups_on_one_stream():
    agent_name, channel_name, _ = _names("doa-twolocal")
    transport = RedisTransport()
    agent = Agent(agent_name, transport=transport)
    channel = Channel(channel_name, transport=transport)

    @agent.subscribe(channel=channel, delete_on_ack=True)
    async def first(message):
        pass

    @agent.subscribe(channel=channel)
    async def second(message):
        pass

    with pytest.raises(RuntimeError, match="other consumer groups"):
        await agent.start()
    await transport.disconnect()


@pytest.mark.asyncio
async def test_delete_on_ack_monitor_turns_deletion_off_for_late_group(
    redis_client, caplog
):
    """A group that joins after startup: the monitor stops deleting on that
    stream (plain XACK) so the newcomer gets every later entry, and logs once."""
    agent_name, channel_name, stream = _names("doa-late")
    group = f"{agent_name}-handler-1"
    transport = RedisTransport(group_monitor_interval_s=0.2)
    agent = Agent(agent_name, transport=transport)
    channel = Channel(channel_name, transport=transport)
    seen = []

    @agent.subscribe(channel=channel, delete_on_ack=True)
    async def handler(message):
        seen.append(message["n"])

    await agent.start()
    try:
        await channel.publish({"type": "t", "n": 1})
        await _wait_for(lambda: _xlen_is(redis_client, stream, 0))  # deleting

        with caplog.at_level(logging.ERROR, logger="eggai.transport.redis"):
            await redis_client.xgroup_create(stream, "late-joiner", id="$")
            await _wait_for(lambda: _async("late-joiner" in caplog.text))
            await asyncio.sleep(0.6)  # several more monitor cycles
        assert caplog.text.count("late-joiner") == 1  # reported once, not per cycle
        assert stream in transport._delete_on_ack_disabled

        await channel.publish({"type": "t", "n": 2})
        await _wait_for(lambda: _async(seen == [1, 2]))
        await asyncio.sleep(0.3)
        assert await redis_client.xlen(stream) == 1  # acked, kept for late-joiner
        assert _pending(await redis_client.xpending(stream, group)) == 0
    finally:
        await agent.stop()


@pytest.mark.asyncio
async def test_delete_on_ack_client_is_open_before_consumers_start():
    """A backlog handled right at startup must find the delete client open."""
    agent_name, channel_name, _ = _names("doa-order")
    transport = RedisTransport()
    agent = Agent(agent_name, transport=transport)
    channel = Channel(channel_name, transport=transport)

    @agent.subscribe(channel=channel, delete_on_ack=True)
    async def handler(message):
        pass

    client_at_start = []
    original_start = transport.broker.start

    async def recording_start(*args, **kwargs):
        client_at_start.append(transport._delete_client)
        return await original_start(*args, **kwargs)

    transport.broker.start = recording_start
    await agent.start()
    try:
        assert client_at_start and client_at_start[0] is not None
    finally:
        await agent.stop()


@pytest.mark.asyncio
async def test_reclaimer_ack_respects_runtime_disabled_streams():
    """Once the monitor disables deletion on a stream, the reclaimer's moves to
    .retry / the DLQ fall back to a plain XACK too."""
    from unittest.mock import AsyncMock, MagicMock

    from eggai.transport.pending_reclaimer import (
        PendingReclaimerManager,
        ReclaimerConfig,
    )

    disabled: set[str] = set()
    manager = PendingReclaimerManager(
        "redis://localhost:6379", delete_on_ack_disabled=disabled
    )
    client = MagicMock()
    client.xack = AsyncMock()
    manager._redis_client = client
    config = ReclaimerConfig(
        stream="s",
        group="g",
        consumer="c",
        retry_stream="s.retry",
        min_idle_ms=1,
        interval_s=1.0,
        delete_on_ack=True,
    )

    disabled.add("s")
    await manager._ack(config, b"1-0")
    client.xack.assert_awaited_once_with("s", "g", b"1-0")
    client.pipeline.assert_not_called()


@pytest.mark.asyncio
async def test_delete_on_ack_awaits_callable_with_async_call():
    """An object with an async __call__ must be awaited, not sent to a thread
    where its coroutine would be created and dropped."""
    calls = []

    class Handler:
        async def __call__(self, message):
            calls.append(message)
            return "done"

    transport = RedisTransport()
    wrapped = transport._wrap_delete_on_ack(Handler(), "g", AckPolicy.NACK_ON_ERROR)
    # Outside a FastStream consume there is no current message: nothing to delete.
    assert await wrapped({"n": 1}) == "done"
    assert calls == [{"n": 1}]


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
