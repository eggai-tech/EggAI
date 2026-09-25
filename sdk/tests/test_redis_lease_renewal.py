"""
lease_renewal: entries a handler is still working on are renewed (XCLAIM ...
JUSTID), so the SDK reclaimer does not redeliver them while they run. Plus the
max_processing_ms deadline. Integration tests against a real Redis at
localhost:6379, and unit tests of the keeper and the handler wrapper.
"""

import asyncio
import logging
import uuid
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
import redis.asyncio as redis
from faststream import AckPolicy

from eggai import Agent, Channel
from eggai.transport import LeaseLostError, ProcessingTimeoutError, RedisTransport
from eggai.transport.lease import (
    _RENEW_SCRIPT,
    LeaseConfig,
    LeaseKeeper,
    LeaseManager,
    resolve_lease_options,
    wrap_handler_with_lease,
)
from eggai.transport.redis import _CONSUMER_INSTANCE

# Reclaim threshold used by the integration tests: handlers below run for
# several multiples of it, so without a lease they are always redelivered.
IDLE_MS = 500
RECLAIM_S = 0.2


async def _wait_for(predicate, timeout=10.0, interval=0.05):
    deadline = asyncio.get_running_loop().time() + timeout
    while True:
        if await predicate():
            return
        if asyncio.get_running_loop().time() > deadline:
            raise AssertionError("condition not met before timeout")
        await asyncio.sleep(interval)


async def _true(value):
    return value


@pytest_asyncio.fixture
async def redis_client():
    client = redis.Redis(host="localhost", port=6379, decode_responses=True)
    yield client
    await client.aclose()


def _names(prefix):
    test_id = uuid.uuid4().hex[:8]
    agent_name = f"{prefix}-{test_id}"
    channel_name = f"{prefix}-ch-{test_id}"
    group = f"{agent_name}-handler-1"
    return agent_name, channel_name, f"eggai.{channel_name}", group


async def _read_as(stream, group, consumer):
    """XREADGROUP one entry as ``consumer`` (binary client: FastStream bodies)."""
    client = redis.Redis(host="localhost", port=6379)
    try:
        await client.xreadgroup(group, consumer, {stream: ">"}, count=1)
    finally:
        await client.aclose()


async def _pending_entries(client, stream, group):
    return await client.xpending_range(stream, group, min="-", max="+", count=100)


class _Tracker:
    """Counts handler runs and how many overlap."""

    def __init__(self):
        self.calls: list[dict] = []
        self.active = 0
        self.max_active = 0
        self.done = 0

    async def run(self, message, seconds):
        self.calls.append(message)
        self.active += 1
        self.max_active = max(self.max_active, self.active)
        try:
            await asyncio.sleep(seconds)
        finally:
            self.active -= 1
        self.done += 1


# --------------------------------------------------------------------------
# Exactly once with a lease, twice without
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_slow_handler_processed_once_with_lease_renewal(redis_client):
    agent_name, channel_name, stream, group = _names("lease-once")
    transport = RedisTransport()
    agent = Agent(agent_name, transport=transport)
    channel = Channel(channel_name, transport=transport)
    tracker = _Tracker()
    samples = []

    @agent.subscribe(
        channel=channel,
        retry_on_idle_ms=IDLE_MS,
        retry_reclaim_interval_s=RECLAIM_S,
        lease_renewal=True,
    )
    async def handler(message):
        await tracker.run(message, 2.0)  # 4x retry_on_idle_ms

    await agent.start()
    try:
        await channel.publish({"type": "t", "n": 1})
        await _wait_for(lambda: _true(tracker.active == 1))
        # While it runs: idle stays below the threshold, owner and delivery
        # count unchanged (JUSTID does not bump it).
        for _ in range(8):
            await asyncio.sleep(0.2)
            (entry,) = await _pending_entries(redis_client, stream, group)
            samples.append(entry)
        await _wait_for(lambda: _true(tracker.done == 1))
        await asyncio.sleep(1.5)  # several more reclaim cycles
    finally:
        await agent.stop()

    assert len(tracker.calls) == 1
    assert tracker.max_active == 1
    assert all(s["time_since_delivered"] < IDLE_MS for s in samples), samples
    assert all(s["times_delivered"] == 1 for s in samples), samples
    assert {s["consumer"] for s in samples} == {f"{group}-{_CONSUMER_INSTANCE}"}
    assert await _pending_entries(redis_client, stream, group) == []
    assert await redis_client.xlen(f"{stream}.{group}.retry") == 0


@pytest.mark.asyncio
async def test_slow_handler_processed_twice_without_lease_renewal():
    """Contrast (the bug): the same slow handler is redelivered while it runs."""
    agent_name, channel_name, _stream, _group = _names("lease-off")
    transport = RedisTransport()
    agent = Agent(agent_name, transport=transport)
    channel = Channel(channel_name, transport=transport)
    tracker = _Tracker()

    @agent.subscribe(
        channel=channel,
        retry_on_idle_ms=IDLE_MS,
        retry_reclaim_interval_s=RECLAIM_S,
    )
    async def handler(message):
        await tracker.run(message, 2.0)

    await agent.start()
    try:
        await channel.publish({"type": "t", "n": 1})
        await _wait_for(lambda: _true(len(tracker.calls) >= 2), timeout=5.0)
    finally:
        await agent.stop()

    assert tracker.max_active == 2  # in parallel
    assert tracker.calls[1]["_retry_count"] == "1"
    assert transport._lease_manager is None  # default: nothing new runs


# --------------------------------------------------------------------------
# Crash recovery still works
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_crashed_consumers_entry_is_still_reclaimed(redis_client):
    """An entry read by a consumer that died (no renewals, no ack) is reclaimed
    after retry_on_idle_ms and handled via the retry stream, even though this
    subscription renews its own leases."""
    agent_name, channel_name, stream, group = _names("lease-crash")
    await redis_client.xgroup_create(stream, group, id="$", mkstream=True)
    producer = RedisTransport()
    await producer.connect()
    try:
        await producer.publish(stream, {"type": "t", "n": 1})
    finally:
        await producer.disconnect()
    # The "crashed" worker: read it, then never ack or renew it.
    await _read_as(stream, group, "crashed-worker")

    transport = RedisTransport()
    agent = Agent(agent_name, transport=transport)
    channel = Channel(channel_name, transport=transport)
    seen = []

    @agent.subscribe(
        channel=channel,
        retry_on_idle_ms=IDLE_MS,
        retry_reclaim_interval_s=RECLAIM_S,
        lease_renewal=True,
    )
    async def handler(message):
        seen.append(message)

    await agent.start()
    try:
        await _wait_for(lambda: _true(len(seen) == 1))
    finally:
        await agent.stop()
    assert seen[0]["n"] == 1
    assert seen[0]["_retry_count"] == "1"


@pytest.mark.asyncio
async def test_renewal_stopping_mid_run_lets_the_entry_be_reclaimed(redis_client):
    """If renewal stops (what a crash looks like from Redis) the entry is
    reclaimed after retry_on_idle_ms, as without the option."""
    agent_name, channel_name, stream, group = _names("lease-stop")
    transport = RedisTransport()
    agent = Agent(agent_name, transport=transport)
    channel = Channel(channel_name, transport=transport)
    tracker = _Tracker()

    @agent.subscribe(
        channel=channel,
        retry_on_idle_ms=IDLE_MS,
        retry_reclaim_interval_s=RECLAIM_S,
        lease_renewal=True,
        cancel_on_lease_lost=False,
    )
    async def handler(message):
        await tracker.run(message, 0.0 if message.get("_retry_count") else 3.0)

    await agent.start()
    try:
        await channel.publish({"type": "t"})
        await _wait_for(lambda: _true(tracker.active == 1))
        assert transport._lease_manager is not None
        for task in transport._lease_manager._tasks.values():
            task.cancel()
        await _wait_for(lambda: _true(len(tracker.calls) == 2), timeout=5.0)
    finally:
        await agent.stop()
    assert tracker.calls[1]["_retry_count"] == "1"


@pytest.mark.asyncio
async def test_stale_entry_of_same_consumer_name_is_not_renewed(redis_client):
    """An entry left in this consumer name's PEL by an earlier incarnation (same
    host and pid after a container restart) is older than anything this process
    reads, so the prefetch scan skips it and the reclaimer recovers it while a
    leased handler is running."""
    agent_name, channel_name, stream, group = _names("lease-stale")
    consumer = f"{group}-{_CONSUMER_INSTANCE}"
    await redis_client.xgroup_create(stream, group, id="$", mkstream=True)
    producer = RedisTransport()
    await producer.connect()
    try:
        await producer.publish(stream, {"type": "t", "n": "stale"})
    finally:
        await producer.disconnect()
    await _read_as(stream, group, consumer)

    transport = RedisTransport()
    agent = Agent(agent_name, transport=transport)
    channel = Channel(channel_name, transport=transport)
    seen = []
    slow_done = asyncio.Event()

    @agent.subscribe(
        channel=channel,
        retry_on_idle_ms=IDLE_MS,
        retry_reclaim_interval_s=RECLAIM_S,
        lease_renewal=True,
        max_records=10,  # prefetch scan on
    )
    async def handler(message):
        seen.append((message["n"], message.get("_retry_count", "0")))
        if message["n"] == "slow":
            await asyncio.sleep(2.0)
            slow_done.set()

    await agent.start()
    try:
        await channel.publish({"type": "t", "n": "slow"})
        await asyncio.wait_for(slow_done.wait(), timeout=10.0)
        await asyncio.sleep(0.5)
    finally:
        await agent.stop()
    assert ("stale", "1") in seen  # reclaimed while "slow" held a lease
    assert [s for s in seen if s[0] == "slow"] == [("slow", "0")]


# --------------------------------------------------------------------------
# Lost leases
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_lost_lease_cancels_the_handler(redis_client, caplog):
    agent_name, channel_name, stream, group = _names("lease-lost")
    transport = RedisTransport()
    agent = Agent(agent_name, transport=transport)
    channel = Channel(channel_name, transport=transport)
    started = asyncio.Event()
    cancelled = asyncio.Event()
    calls = []

    @agent.subscribe(
        channel=channel,
        retry_on_idle_ms=IDLE_MS,
        retry_reclaim_interval_s=RECLAIM_S,
        lease_renewal=True,
        max_retries=None,
    )
    async def handler(message):
        calls.append(message.get("_retry_count", "0"))
        if len(calls) > 1:
            return
        started.set()
        try:
            await asyncio.sleep(30)
        except asyncio.CancelledError:
            cancelled.set()
            raise

    caplog.set_level(logging.ERROR)
    await agent.start()
    try:
        await channel.publish({"type": "t"})
        await asyncio.wait_for(started.wait(), timeout=10.0)
        (entry,) = await _pending_entries(redis_client, stream, group)
        # Someone else takes the entry (what the reclaimer does after renewals
        # failed for longer than retry_on_idle_ms).
        await redis_client.xclaim(
            stream, group, "someone-else", 0, [entry["message_id"]], justid=True
        )
        await asyncio.wait_for(cancelled.wait(), timeout=3.0)
        await _wait_for(lambda: _true("LeaseLostError" in caplog.text))
        # Not acked by the cancelled run: still in the PEL, under its new owner.
        pending = await _pending_entries(redis_client, stream, group)
        assert f"{group}-{_CONSUMER_INSTANCE}" not in {p["consumer"] for p in pending}
    finally:
        await agent.stop()
    assert "Lease lost for entry" in caplog.text


@pytest.mark.asyncio
async def test_lost_lease_without_cancel_lets_the_handler_finish(redis_client, caplog):
    agent_name, channel_name, stream, group = _names("lease-keep")
    transport = RedisTransport()
    agent = Agent(agent_name, transport=transport)
    channel = Channel(channel_name, transport=transport)
    started = asyncio.Event()
    finished = asyncio.Event()

    @agent.subscribe(
        channel=channel,
        retry_on_idle_ms=IDLE_MS,
        retry_reclaim_interval_s=RECLAIM_S,
        lease_renewal=True,
        cancel_on_lease_lost=False,
    )
    async def handler(message):
        if message.get("_retry_count"):
            return
        started.set()
        await asyncio.sleep(1.0)
        finished.set()

    caplog.set_level(logging.ERROR)
    await agent.start()
    try:
        await channel.publish({"type": "t"})
        await asyncio.wait_for(started.wait(), timeout=10.0)
        (entry,) = await _pending_entries(redis_client, stream, group)
        await redis_client.xack(stream, group, entry["message_id"])
        await asyncio.wait_for(finished.wait(), timeout=5.0)
    finally:
        await agent.stop()
    assert "keeps running" in caplog.text
    assert "LeaseLostError" not in caplog.text


@pytest.mark.asyncio
async def test_trimmed_entry_is_not_a_lost_lease(redis_client, caplog):
    """An entry deleted from the stream can't be redelivered: let it finish."""
    agent_name, channel_name, stream, group = _names("lease-trim")
    transport = RedisTransport()
    agent = Agent(agent_name, transport=transport)
    channel = Channel(channel_name, transport=transport)
    started = asyncio.Event()
    finished = asyncio.Event()

    @agent.subscribe(
        channel=channel,
        retry_on_idle_ms=IDLE_MS,
        retry_reclaim_interval_s=RECLAIM_S,
        lease_renewal=True,
    )
    async def handler(message):
        started.set()
        await asyncio.sleep(1.5)
        finished.set()

    caplog.set_level(logging.WARNING)
    await agent.start()
    try:
        await channel.publish({"type": "t"})
        await asyncio.wait_for(started.wait(), timeout=10.0)
        (entry,) = await _pending_entries(redis_client, stream, group)
        await redis_client.xdel(stream, entry["message_id"])
        await asyncio.wait_for(finished.wait(), timeout=5.0)
        await asyncio.sleep(0.3)
    finally:
        await agent.stop()
    assert "was deleted from stream" in caplog.text
    assert "LeaseLostError" not in caplog.text
    assert await _pending_entries(redis_client, stream, group) == []


# --------------------------------------------------------------------------
# Retry stream, prefetch, batch
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_retry_stream_delivery_is_renewed(redis_client):
    """A redelivery is a new entry on the .retry stream with its own group and
    consumer: that one is renewed too."""
    agent_name, channel_name, stream, group = _names("lease-retry")
    retry_stream = f"{stream}.{group}.retry"
    retry_group = f"{group}-retry"
    transport = RedisTransport()
    agent = Agent(agent_name, transport=transport)
    channel = Channel(channel_name, transport=transport)
    tracker = _Tracker()
    samples = []

    @agent.subscribe(
        channel=channel,
        retry_on_idle_ms=IDLE_MS,
        retry_reclaim_interval_s=RECLAIM_S,
        lease_renewal=True,
    )
    async def handler(message):
        if not message.get("_retry_count"):
            raise RuntimeError("transient")  # fast failure, NACK -> retry
        await tracker.run(message, 2.0)

    await agent.start()
    try:
        await channel.publish({"type": "t"})
        await _wait_for(lambda: _true(tracker.active == 1))
        for _ in range(8):
            await asyncio.sleep(0.2)
            (entry,) = await _pending_entries(redis_client, retry_stream, retry_group)
            samples.append(entry)
        await _wait_for(lambda: _true(tracker.done == 1))
        await asyncio.sleep(1.5)
    finally:
        await agent.stop()

    assert [c["_retry_count"] for c in tracker.calls] == ["1"]
    assert all(s["time_since_delivered"] < IDLE_MS for s in samples), samples
    assert {s["consumer"] for s in samples} == {f"{retry_group}-{_CONSUMER_INSTANCE}"}
    assert await _pending_entries(redis_client, retry_stream, retry_group) == []


async def _prefill(stream, group, n):
    """Publish n entries before the group's consumer starts (read in one go)."""
    producer = RedisTransport()
    await producer.connect()
    try:
        for i in range(n):
            await producer.publish(stream, {"type": "t", "n": i})
    finally:
        await producer.disconnect()


@pytest.mark.asyncio
@pytest.mark.parametrize("lease", [True, False])
async def test_prefetched_entries_are_renewed(redis_client, lease):
    """max_records=5 reads the whole backlog into this consumer's PEL; the ones
    queued behind a slow handler are renewed too (and redelivered without)."""
    agent_name, channel_name, stream, group = _names("lease-prefetch")
    await _prefill(stream, group, 3)
    transport = RedisTransport()
    agent = Agent(agent_name, transport=transport)
    channel = Channel(channel_name, transport=transport)
    tracker = _Tracker()
    options = {"lease_renewal": True} if lease else {}

    @agent.subscribe(
        channel=channel,
        group_start="0",
        max_records=5,
        retry_on_idle_ms=IDLE_MS,
        retry_reclaim_interval_s=RECLAIM_S,
        **options,
    )
    async def handler(message):
        await tracker.run(message, 0.8)

    await agent.start()
    try:
        await _wait_for(lambda: _true(tracker.done >= 3), timeout=10.0)
        await asyncio.sleep(1.0)
    finally:
        await agent.stop()
    retried = [c for c in tracker.calls if c.get("_retry_count")]
    if lease:
        assert sorted(c["n"] for c in tracker.calls) == [0, 1, 2]
        assert retried == []
    else:
        assert retried  # the queued ones went idle and were redelivered


@pytest.mark.asyncio
@pytest.mark.parametrize("lease", [True, False])
async def test_concurrent_workers_entries_are_renewed(redis_client, lease):
    """max_workers=2: FastStream keeps reading while two handlers run, and the
    entries waiting for a worker slot are renewed too (redelivered without)."""
    agent_name, channel_name, stream, group = _names("lease-workers")
    await _prefill(stream, group, 5)
    transport = RedisTransport()
    agent = Agent(agent_name, transport=transport)
    channel = Channel(channel_name, transport=transport)
    tracker = _Tracker()

    @agent.subscribe(
        channel=channel,
        group_start="0",
        max_workers=2,
        retry_on_idle_ms=IDLE_MS,
        retry_reclaim_interval_s=RECLAIM_S,
        **({"lease_renewal": True} if lease else {}),
    )
    async def handler(message):
        await tracker.run(message, 0.8)

    await agent.start()
    try:
        await _wait_for(lambda: _true(tracker.done >= 5), timeout=15.0)
        await asyncio.sleep(1.0)
    finally:
        await agent.stop()
    retried = [c for c in tracker.calls if c.get("_retry_count")]
    if lease:
        assert sorted(c["n"] for c in tracker.calls) == [0, 1, 2, 3, 4]
        assert retried == []
    else:
        assert retried


@pytest.mark.asyncio
async def test_lease_renewal_defaults_max_records_to_one(redis_client):
    agent_name, channel_name, stream, group = _names("lease-one")
    await _prefill(stream, group, 3)
    transport = RedisTransport()
    agent = Agent(agent_name, transport=transport)
    channel = Channel(channel_name, transport=transport)
    tracker = _Tracker()
    pending_counts = []

    @agent.subscribe(
        channel=channel,
        group_start="0",
        retry_on_idle_ms=IDLE_MS,
        retry_reclaim_interval_s=RECLAIM_S,
        lease_renewal=True,
    )
    async def handler(message):
        pending_counts.append(len(await _pending_entries(redis_client, stream, group)))
        await tracker.run(message, 0.3)

    await agent.start()
    try:
        await _wait_for(lambda: _true(tracker.done == 3))
    finally:
        await agent.stop()
    assert pending_counts == [1, 1, 1]  # one entry read at a time


@pytest.mark.asyncio
async def test_batch_entries_are_all_renewed(redis_client):
    agent_name, channel_name, stream, group = _names("lease-batch")
    await _prefill(stream, group, 3)
    transport = RedisTransport()
    agent = Agent(agent_name, transport=transport)
    channel = Channel(channel_name, transport=transport)
    batches = []
    samples = []

    @agent.subscribe(
        channel=channel,
        group_start="0",
        batch=True,
        max_records=10,
        retry_on_idle_ms=IDLE_MS,
        retry_reclaim_interval_s=RECLAIM_S,
        lease_renewal=True,
    )
    async def handler(messages: list):
        batches.append(messages)
        for _ in range(8):
            await asyncio.sleep(0.2)
            samples.extend(await _pending_entries(redis_client, stream, group))

    await agent.start()
    try:
        await _wait_for(lambda: _true(len(batches) >= 1 and len(samples) >= 24))
        await asyncio.sleep(1.0)
    finally:
        await agent.stop()
    assert len(batches) == 1 and len(batches[0]) == 3
    assert all(s["time_since_delivered"] < IDLE_MS for s in samples), samples


# --------------------------------------------------------------------------
# max_processing_ms
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_max_processing_ms_cancels_and_retries(caplog):
    agent_name, channel_name, _stream, _group = _names("lease-deadline")
    transport = RedisTransport()
    agent = Agent(agent_name, transport=transport)
    channel = Channel(channel_name, transport=transport)
    cancelled = asyncio.Event()
    retried = asyncio.Event()

    @agent.subscribe(
        channel=channel,
        retry_on_idle_ms=IDLE_MS,
        retry_reclaim_interval_s=RECLAIM_S,
        lease_renewal=True,
        max_processing_ms=300,
    )
    async def handler(message):
        if message.get("_retry_count") == "1":
            retried.set()
            return
        try:
            await asyncio.sleep(30)  # hung call
        except asyncio.CancelledError:
            cancelled.set()
            raise

    caplog.set_level(logging.ERROR)
    await agent.start()
    try:
        await channel.publish({"type": "t"})
        await asyncio.wait_for(cancelled.wait(), timeout=10.0)
        await asyncio.wait_for(retried.wait(), timeout=10.0)
    finally:
        await agent.stop()
    assert "ProcessingTimeoutError" in caplog.text


# --------------------------------------------------------------------------
# Lifecycle
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_agent_stop_cancels_handler_and_stops_renewal():
    agent_name, channel_name, _stream, _group = _names("lease-shutdown")
    transport = RedisTransport(graceful_timeout=0.5)
    agent = Agent(agent_name, transport=transport)
    channel = Channel(channel_name, transport=transport)
    started = asyncio.Event()
    cancelled = asyncio.Event()

    @agent.subscribe(
        channel=channel,
        retry_on_idle_ms=IDLE_MS,
        retry_reclaim_interval_s=RECLAIM_S,
        lease_renewal=True,
    )
    async def handler(message):
        started.set()
        try:
            await asyncio.sleep(30)
        except asyncio.CancelledError:
            cancelled.set()
            raise

    await agent.start()
    manager = transport._lease_manager
    assert manager is not None and manager.client is not None
    tasks = list(manager._tasks.values())
    assert len(tasks) == 2  # main stream + retry stream
    await channel.publish({"type": "t"})
    await asyncio.wait_for(started.wait(), timeout=10.0)
    await asyncio.wait_for(agent.stop(), timeout=10.0)
    assert cancelled.is_set()
    assert all(t.done() for t in tasks)
    assert manager.client is None and manager._tasks == {}
    assert all(not k.in_flight for k in manager._keepers.values())


# --------------------------------------------------------------------------
# The renewal script against a real Redis
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_renew_script_statuses(redis_client):
    stream = f"lease-script-{uuid.uuid4().hex[:8]}"
    group, me = "g", "me"
    await redis_client.xgroup_create(stream, group, id="$", mkstream=True)
    ids = [await redis_client.xadd(stream, {"k": str(i)}) for i in range(3)]
    await redis_client.xreadgroup(group, me, {stream: ">"})
    await asyncio.sleep(0.3)
    await redis_client.xclaim(stream, group, "other", 0, [ids[1]], justid=True)
    await redis_client.xdel(stream, ids[2])
    script = redis_client.register_script(_RENEW_SCRIPT)
    missing = "1-1"

    statuses = await script(keys=[stream], args=[group, me, *ids, missing])

    assert statuses == [1, 0, 2, 0]  # renewed, other owner, trimmed, not pending
    pending = {
        p["message_id"]: p
        for p in await redis_client.xpending_range(stream, group, "-", "+", 10)
    }
    assert pending[ids[0]]["consumer"] == me
    assert pending[ids[0]]["time_since_delivered"] < 100  # idle reset
    assert pending[ids[0]]["times_delivered"] == 1  # JUSTID: count unchanged
    assert pending[ids[1]]["consumer"] == "other"  # not stolen back
    await redis_client.delete(stream)


# --------------------------------------------------------------------------
# Keeper / wrapper unit tests (no Redis)
# --------------------------------------------------------------------------


def _keeper(**overrides):
    config = {
        "stream": "s",
        "group": "g",
        "consumer": "c",
        "interval_s": 0.05,
        **overrides,
    }
    return LeaseKeeper(LeaseConfig(**config))


def _manager(script):
    manager = LeaseManager("redis://unused")
    manager.client = object()  # type: ignore[assignment]
    manager.script = script
    manager.running = True
    return manager


@pytest.mark.asyncio
async def test_renewal_failure_is_logged_and_retried(caplog):
    keeper = _keeper()
    keeper.begin(["5-0"])
    script = AsyncMock(side_effect=[ConnectionError("redis down"), [1], [1], [1]])
    manager = _manager(script)
    caplog.set_level(logging.WARNING)
    task = asyncio.create_task(keeper.run(manager))
    try:
        await _wait_for(lambda: _true(script.await_count >= 2), timeout=2.0)
    finally:
        manager.running = False
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
    assert "Lease renewal failed" in caplog.text
    assert "stream=s group=g consumer=c ids=['5-0']" in caplog.text
    assert "ConnectionError: redis down" in caplog.text


@pytest.mark.asyncio
async def test_hung_renewal_call_is_bounded(caplog):
    keeper = _keeper(interval_s=0.1)
    keeper.begin(["5-0"])

    async def hang(**_kwargs):
        await asyncio.sleep(10)

    manager = _manager(hang)
    caplog.set_level(logging.WARNING)
    task = asyncio.create_task(keeper.run(manager))
    try:
        await _wait_for(lambda: _true("TimeoutError" in caplog.text), timeout=2.0)
    finally:
        manager.running = False
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)


@pytest.mark.asyncio
async def test_renewal_skips_when_nothing_in_flight():
    keeper = _keeper()
    script = AsyncMock(return_value=[])
    await keeper.renew_once(object(), script)
    script.assert_not_awaited()


@pytest.mark.asyncio
async def test_lost_status_cancels_only_its_invocation():
    keeper = _keeper()
    blocker = asyncio.Event()
    lost_task = asyncio.create_task(blocker.wait())
    kept_task = asyncio.create_task(blocker.wait())
    lost, kept = keeper.begin(["1-0"]), keeper.begin(["2-0"])
    lost.task, kept.task = lost_task, kept_task

    await keeper.renew_once(object(), AsyncMock(return_value=[0, 1]))
    await asyncio.sleep(0)

    assert lost_task.cancelled() and lost.reason == "lease_lost"
    assert not kept_task.done() and kept.reason is None
    kept_task.cancel()


@pytest.mark.asyncio
async def test_finished_failures_are_not_renewed_by_the_prefetch_scan():
    """A failed entry stays in the PEL for retry: never renew it."""
    keeper = _keeper(scan_prefetched=True)
    older = keeper.begin(["1-0"])
    failed = keeper.begin(["2-0"])
    keeper.end(failed)  # handler raised: NACKed, still pending
    client = AsyncMock()
    client.xpending_range.return_value = [
        {"message_id": "1-0"},
        {"message_id": "2-0"},
        {"message_id": "3-0"},  # prefetched, queued
    ]
    script = AsyncMock(return_value=[1, 1])

    await keeper.renew_once(client, script)

    assert script.await_args.kwargs["args"] == ["g", "c", "1-0", "3-0"]
    keeper.end(older)


@pytest.mark.asyncio
async def test_queued_entry_lost_before_start_raises_without_running():
    keeper = _keeper(scan_prefetched=True)
    running = keeper.begin(["1-0"])
    client = AsyncMock()
    client.xpending_range.return_value = [{"message_id": "1-0"}, {"message_id": "2-0"}]
    await keeper.renew_once(client, AsyncMock(return_value=[1, 0]))
    keeper.end(running)
    called = []

    async def handler(message):
        called.append(message)

    wrapped = wrap_handler_with_lease(
        handler,
        stream="s",
        group="g",
        keeper=keeper,
        message_ids=lambda: ["2-0"],
        max_processing_ms=None,
    )
    with pytest.raises(LeaseLostError) as exc:
        await wrapped({"n": 2})
    assert called == []
    assert exc.value.message_ids == ("2-0",)
    assert not keeper.in_flight


@pytest.mark.asyncio
async def test_wrapper_passes_results_and_errors_through_and_releases():
    keeper = _keeper()

    async def ok(message):
        return message["n"] * 2

    async def boom(message):
        raise ValueError("handler failed")

    def sync_ok(message):
        return "sync"

    def wrap(handler):
        return wrap_handler_with_lease(
            handler,
            stream="s",
            group="g",
            keeper=keeper,
            message_ids=lambda: ["7-0"],
            max_processing_ms=None,
        )

    assert await wrap(ok)({"n": 21}) == 42
    assert await wrap(sync_ok)({"n": 1}) == "sync"
    with pytest.raises(ValueError, match="handler failed"):
        await wrap(boom)({"n": 1})
    assert not keeper.in_flight


@pytest.mark.asyncio
async def test_wrapper_forwards_outer_cancellation():
    keeper = _keeper()
    started = asyncio.Event()
    inner_cancelled = asyncio.Event()

    async def handler(message):
        started.set()
        try:
            await asyncio.sleep(30)
        except asyncio.CancelledError:
            inner_cancelled.set()
            raise

    wrapped = wrap_handler_with_lease(
        handler,
        stream="s",
        group="g",
        keeper=keeper,
        message_ids=lambda: ["7-0"],
        max_processing_ms=None,
    )
    outer = asyncio.create_task(wrapped({}))
    await started.wait()
    outer.cancel()
    with pytest.raises(asyncio.CancelledError):
        await outer
    assert inner_cancelled.is_set()
    assert not keeper.in_flight


@pytest.mark.asyncio
async def test_deadline_raises_processing_timeout_error():
    async def handler(message):
        await asyncio.sleep(30)

    wrapped = wrap_handler_with_lease(
        handler,
        stream="s",
        group="g",
        keeper=None,
        message_ids=lambda: None,
        max_processing_ms=50,
    )
    with pytest.raises(ProcessingTimeoutError) as exc:
        await wrapped({})
    assert exc.value.max_processing_ms == 50
    assert isinstance(exc.value, TimeoutError)


# --------------------------------------------------------------------------
# Option validation and defaults
# --------------------------------------------------------------------------


def test_default_interval_is_a_third_of_retry_on_idle_ms():
    opts = resolve_lease_options({"lease_renewal": True}, 900)
    assert opts.interval_ms == 300
    assert opts.cancel_on_lease_lost is True
    assert resolve_lease_options({}, 900).lease_renewal is False


@pytest.mark.parametrize(
    ("options", "match"),
    [
        ({"lease_renewal": True}, "lease_renewal requires retry_on_idle_ms"),
        (
            {
                "lease_renewal": True,
                "retry_on_idle_ms": 500,
                "lease_renewal_interval_ms": 500,
            },
            "must be < retry_on_idle_ms",
        ),
        (
            {
                "lease_renewal": True,
                "retry_on_idle_ms": 500,
                "lease_renewal_interval_ms": 0,
            },
            "must be a positive int",
        ),
        (
            {"retry_on_idle_ms": 500, "lease_renewal_interval_ms": 100},
            "require lease_renewal=True",
        ),
        (
            {"retry_on_idle_ms": 500, "cancel_on_lease_lost": False},
            "require lease_renewal=True",
        ),
        ({"max_processing_ms": 1000}, "max_processing_ms requires retry_on_idle_ms"),
        (
            {"retry_on_idle_ms": 500, "max_processing_ms": 0},
            "max_processing_ms must be a positive int",
        ),
        ({"lease_renewal": "yes", "retry_on_idle_ms": 500}, "True or False"),
    ],
)
def test_agent_subscribe_validates_lease_options(options, match):
    agent = Agent("lease-validation", transport=RedisTransport())
    channel = Channel("lease-validation", transport=agent._get_transport())

    with pytest.raises(ValueError, match=match):

        @agent.subscribe(channel=channel, **options)
        async def handler(message):
            pass


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("options", "match"),
    [
        ({"lease_renewal": True}, "lease_renewal requires retry_on_idle_ms"),
        (
            {"lease_renewal": True, "retry_on_idle_ms": 500, "no_ack": True},
            "incompatible with no_ack",
        ),
        (
            {
                "lease_renewal": True,
                "retry_on_idle_ms": 500,
                "ack_policy": AckPolicy.MANUAL,
            },
            "incompatible with ack_policy=AckPolicy.MANUAL",
        ),
        (
            {"lease_renewal": True, "retry_on_idle_ms": 500, "group": "g"},
            "requires a consumer name",
        ),
    ],
)
async def test_transport_subscribe_validates_lease_options(options, match):
    transport = RedisTransport()
    if "group" not in options:
        options = {"handler_id": "lease-val-h", **options}

    async def handler(message):
        pass

    with pytest.raises(ValueError, match=match):
        await transport.subscribe("lease-val", handler, **options)
    assert transport._lease_manager is None or not transport._lease_manager._keepers
