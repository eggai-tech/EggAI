"""
Shared DLQ channel (``dlq_channel``) tests.

Covers three layers:

- pure helpers in ``pending_reclaimer`` (envelope re-encoding, provenance
  injection, poison wrapping) — no Redis needed;
- subscribe-time wiring and validation in ``RedisTransport`` / ``Agent`` /
  ``Channel`` — builds configs without connecting;
- end-to-end against a live Redis: two failing handlers on two channels
  dead-letter into ONE stream, a sink that starts *after* the failures consumes
  it with ``group_start="0"`` and reads the provenance keys, and a poison entry
  is wrapped so the sink still receives a JSON object.

The file name contains "redis" so ``conftest.py`` skips the whole module when
no Redis is listening on localhost:6379.
"""

import asyncio
import base64
import json
import uuid

import pytest
import redis.asyncio as redis
from faststream.redis.parser.binary import BinaryMessageFormatV1

from eggai import Agent, Channel
from eggai.channel import NAMESPACE, resolve_dlq_channel
from eggai.transport import RedisTransport
from eggai.transport.base import Transport
from eggai.transport.pending_reclaimer import (
    PendingReclaimerManager,
    ReclaimerConfig,
    _dlq_metadata,
    _encode_envelope,
    _parse_entry,
    _poison_body,
    _stamp_dead_letter,
)

# --------------------------------------------------------------------------- #
# Pure helpers (no Redis)
# --------------------------------------------------------------------------- #


def test_resolve_dlq_channel_namespaces_topic_names():
    assert resolve_dlq_channel(None) is None
    assert resolve_dlq_channel("dlq") == f"{NAMESPACE}.dlq"
    assert resolve_dlq_channel(Channel("dlq")) == f"{NAMESPACE}.dlq"
    with pytest.raises(ValueError, match="non-empty"):
        resolve_dlq_channel("")
    with pytest.raises(ValueError, match="non-empty"):
        resolve_dlq_channel(42)  # type: ignore[arg-type]
    # A full key pasted as a string would be namespaced twice → reject loudly.
    with pytest.raises(ValueError, match="already starts with the namespace"):
        resolve_dlq_channel(f"{NAMESPACE}.dlq")
    with pytest.raises(ValueError, match="already starts with the namespace"):
        resolve_dlq_channel(Channel("dlq").get_name())


def test_stamp_dead_letter_resets_budget_and_keeps_first_origin():
    body = {
        "type": "order",
        "data": {"k": 1},
        "_retry_count": "4",
        "_original_message_id": "1-0",
    }
    origin = {
        "_dlq_reason": "max_retries",
        "_dlq_source": "ns.orders",
        "_dlq_handler": "svc-h-1",
        "_dlq_at": "t1",
    }
    _stamp_dead_letter(body, origin, 3)
    assert body["data"] == {"k": 1}  # payload untouched
    assert body["_dlq_source"] == "ns.orders"
    assert body["_dlq_retries"] == "3"
    assert body["_retry_count"] == "0"  # fresh budget for the DLQ consumer
    assert body["_original_message_id"] == "1-0"

    # Dead-lettered a second time (the DLQ consumer itself gave up after 2
    # retries): the original origin wins, the consumer's does not overwrite it.
    sink = {
        "_dlq_reason": "max_retries",
        "_dlq_source": "ns.dlq",
        "_dlq_handler": "sink-1",
        "_dlq_at": "t2",
    }
    body["_retry_count"] = "3"
    _stamp_dead_letter(body, sink, 2)
    assert body["_dlq_source"] == "ns.orders"
    assert body["_dlq_handler"] == "svc-h-1"
    assert body["_dlq_at"] == "t1"
    assert body["_dlq_retries"] == "3"
    assert body["_retry_count"] == "0"


def test_parse_entry_rejects_what_cannot_be_retried():
    assert _parse_entry(b"garbage") is None
    assert _parse_entry(_encode_envelope({}, b"[1,2]")) is None  # JSON array body
    assert _parse_entry(_encode_envelope({}, b'{"_retry_count":"n/a"}')) is None
    parsed = _parse_entry(
        _encode_envelope({"h": "v"}, b'{"type":"t","_retry_count":"2"}')
    )
    assert parsed is not None
    headers, body, count = parsed
    assert headers == {"h": "v"}
    assert body["type"] == "t"
    assert count == 2


def test_poison_body_keeps_raw_bytes_headers_and_zero_budget():
    raw = b"\x00\x01definitely-not-an-envelope"
    headers, body = _poison_body(
        raw, {"_dlq_reason": "poison", "_dlq_source": "ns.o"}, "7-0"
    )
    assert headers == {}
    assert body["_dlq_reason"] == "poison"
    assert body["_dlq_source"] == "ns.o"
    assert body["_original_message_id"] == "7-0"
    assert body["_retry_count"] == "0"
    assert body["_dlq_retries"] == "0"
    assert base64.b64decode(body["_dlq_raw_b64"]) == raw

    # An envelope whose body is unusable keeps its headers (correlation id…).
    env = _encode_envelope({"correlation_id": "c1"}, b"[1,2]")
    headers, body = _poison_body(env, {"_dlq_reason": "poison"}, "8-0")
    assert headers == {"correlation_id": "c1"}
    assert base64.b64decode(body["_dlq_raw_b64"]) == env


def test_dlq_metadata_records_original_channel_not_scanned_stream():
    # The retry reclaimer scans the retry stream; provenance must still name the
    # channel the handler subscribed to.
    cfg = ReclaimerConfig(
        stream="ns.orders.svc-h-1.retry",
        group="svc-h-1-retry",
        consumer="svc-h-1-retry-reclaimer",
        retry_stream="ns.orders.svc-h-1.retry",
        min_idle_ms=1,
        interval_s=1.0,
        source_stream="ns.orders",
        handler="svc-h-1",
    )
    meta = _dlq_metadata(cfg, "max_retries")
    assert meta["_dlq_source"] == "ns.orders"
    assert meta["_dlq_handler"] == "svc-h-1"
    assert meta["_dlq_reason"] == "max_retries"
    assert meta["_dlq_at"].endswith("+00:00")


# --------------------------------------------------------------------------- #
# Wiring + validation (no connection)
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_dlq_channel_shared_by_both_reclaimers_and_across_handlers():
    transport = RedisTransport()

    async def handler_a(message):
        return message

    async def handler_b(message):
        return message

    await transport.subscribe(
        "orders",
        handler_a,
        handler_id="orders-a-1",
        retry_on_idle_ms=500,
        max_retries=3,
        dlq_channel="ops.dlq",
    )
    await transport.subscribe(
        "payments",
        handler_b,
        handler_id="payments-b-1",
        retry_on_idle_ms=500,
        max_retries=3,
        dlq_channel="ops.dlq",
    )

    assert transport._reclaimer_manager is not None
    configs = list(transport._reclaimer_manager._configs.values())
    assert len(configs) == 4  # main + retry reclaimer per handler
    assert {c.dlq_stream for c in configs} == {"ops.dlq"}
    # Retry streams stay per-handler (#225) — only the terminal sink is shared.
    assert {c.retry_stream for c in configs} == {
        "orders.orders-a-1.retry",
        "payments.payments-b-1.retry",
    }
    assert {(c.source_stream, c.handler) for c in configs} == {
        ("orders", "orders-a-1"),
        ("payments", "payments-b-1"),
    }


@pytest.mark.asyncio
async def test_shared_dlq_is_never_trimmed_by_its_writers():
    """XADD MAXLEN trims the whole stream regardless of writer, so a shared DLQ
    must not inherit any single writer's retry_max_len; the per-handler DLQ and
    the retry streams keep the cap."""
    transport = RedisTransport(retry_max_len=250)

    async def handler(message):
        return message

    await transport.subscribe(
        "orders",
        handler,
        handler_id="orders-h-1",
        retry_on_idle_ms=500,
        dlq_channel="ops.dlq",
    )
    await transport.subscribe(
        "payments", handler, handler_id="payments-h-1", retry_on_idle_ms=500
    )
    assert transport._reclaimer_manager is not None
    by_source = {}
    for c in transport._reclaimer_manager._configs.values():
        by_source.setdefault(c.source_stream, set()).add((c.max_len, c.dlq_max_len))
    # Shared DLQ: retry stream still capped, DLQ untrimmed.
    assert by_source["orders"] == {(250, None)}
    # Per-handler default: both capped, as before.
    assert by_source["payments"] == {(250, 250)}


@pytest.mark.asyncio
async def test_dlq_default_unchanged_when_dlq_channel_not_passed():
    transport = RedisTransport()

    async def handler(message):
        return message

    await transport.subscribe(
        "orders",
        handler,
        handler_id="orders-handler-1",
        retry_on_idle_ms=500,
        max_retries=3,
    )
    assert transport._reclaimer_manager is not None
    configs = list(transport._reclaimer_manager._configs.values())
    assert {c.dlq_stream for c in configs} == {"orders.orders-handler-1.dlq"}
    # Provenance is recorded on per-handler DLQs too.
    assert all(
        c.source_stream == "orders" and c.handler == "orders-handler-1" for c in configs
    )


@pytest.mark.asyncio
async def test_dlq_channel_validation_at_transport():
    transport = RedisTransport()

    async def handler(message):
        return message

    with pytest.raises(ValueError, match="requires retry_on_idle_ms"):
        await transport.subscribe(
            "orders", handler, handler_id="h-1", dlq_channel="ops.dlq"
        )
    with pytest.raises(ValueError, match="requires max_retries"):
        await transport.subscribe(
            "orders",
            handler,
            handler_id="h-2",
            retry_on_idle_ms=500,
            max_retries=None,
            dlq_channel="ops.dlq",
        )
    with pytest.raises(ValueError, match="own input"):
        await transport.subscribe(
            "orders",
            handler,
            handler_id="h-3",
            retry_on_idle_ms=500,
            dlq_channel="orders",
        )
    with pytest.raises(ValueError, match="retry stream"):
        await transport.subscribe(
            "orders",
            handler,
            handler_id="h-4",
            retry_on_idle_ms=500,
            dlq_channel="orders.h-4.retry",
        )
    # …and ANOTHER handler's retry stream, which that handler auto-consumes.
    with pytest.raises(ValueError, match="retry stream"):
        await transport.subscribe(
            "orders",
            handler,
            handler_id="h-4b",
            retry_on_idle_ms=500,
            dlq_channel="payments.other-1.retry",
        )
    # Rejected before anything was registered on the broker for that handler.
    assert not any(
        info.group in ("h-4", "h-4b") for info in transport._stream_subscriptions
    )
    with pytest.raises(ValueError, match="non-empty"):
        await transport.subscribe(
            "orders", handler, handler_id="h-5", retry_on_idle_ms=500, dlq_channel=""
        )
    # SDK-managed retries need a consumer group (the reclaimer works on its PEL).
    with pytest.raises(ValueError, match="requires a consumer group"):
        await transport.subscribe("orders", handler, retry_on_idle_ms=500)


class _RecordingTransport(Transport):
    """Captures subscribe kwargs so Agent/Channel-level resolution can be asserted."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    async def connect(self):
        pass

    async def disconnect(self):
        pass

    async def publish(self, channel, message):
        pass

    async def subscribe(self, channel, handler, **kwargs):
        self.calls.append((channel, kwargs))
        return handler


@pytest.mark.asyncio
async def test_agent_subscribe_resolves_dlq_channel_to_namespaced_key():
    transport = _RecordingTransport()
    agent = Agent("svc", transport=transport)

    @agent.subscribe(
        channel=Channel("orders", transport=transport),
        retry_on_idle_ms=500,
        dlq_channel="dlq",  # topic name → namespaced
    )
    async def h_str(message):
        return message

    @agent.subscribe(
        channel=Channel("payments", transport=transport),
        retry_on_idle_ms=500,
        dlq_channel=Channel("dlq"),  # Channel → its own name
    )
    async def h_channel(message):
        return message

    await agent.start()
    try:
        assert [k["dlq_channel"] for _, k in transport.calls] == [
            f"{NAMESPACE}.dlq",
            f"{NAMESPACE}.dlq",
        ]
    finally:
        await agent.stop()


@pytest.mark.asyncio
async def test_agent_subscribe_decorator_reuse_does_not_double_namespace():
    """One decorator object applied to two handlers must not re-namespace the
    already-resolved key (the closure's kwargs are shared between applications)."""
    transport = _RecordingTransport()
    agent = Agent("svc", transport=transport)
    decorate = agent.subscribe(
        channel=Channel("orders", transport=transport),
        retry_on_idle_ms=500,
        dlq_channel="dlq",
    )

    async def h1(message):
        return message

    async def h2(message):
        return message

    decorate(h1)
    decorate(h2)
    await agent.start()
    try:
        assert [k["dlq_channel"] for _, k in transport.calls] == [
            f"{NAMESPACE}.dlq",
            f"{NAMESPACE}.dlq",
        ]
    finally:
        await agent.stop()


def test_agent_subscribe_rejects_bad_dlq_channel_at_decoration_time():
    agent = Agent("svc", transport=_RecordingTransport())
    orders = Channel("orders")

    with pytest.raises(ValueError, match="requires retry_on_idle_ms"):

        @agent.subscribe(channel=orders, dlq_channel="dlq")
        async def h1(message):
            return message

    with pytest.raises(ValueError, match="requires max_retries"):

        @agent.subscribe(
            channel=orders, retry_on_idle_ms=500, max_retries=None, dlq_channel="dlq"
        )
        async def h2(message):
            return message

    with pytest.raises(ValueError, match="own input"):

        @agent.subscribe(channel=orders, retry_on_idle_ms=500, dlq_channel=orders)
        async def h3(message):
            return message

    with pytest.raises(ValueError, match="retry stream"):

        @agent.subscribe(
            channel=orders, retry_on_idle_ms=500, dlq_channel="orders.svc-h3-1.retry"
        )
        async def h4(message):
            return message


@pytest.mark.asyncio
async def test_channel_subscribe_resolves_dlq_channel():
    transport = _RecordingTransport()
    orders = Channel("orders", transport=transport)

    async def handler(message):
        return message

    await orders.subscribe(handler, retry_on_idle_ms=500, dlq_channel="dlq")
    try:
        assert transport.calls[0][1]["dlq_channel"] == f"{NAMESPACE}.dlq"
    finally:
        await orders.stop()


# --------------------------------------------------------------------------- #
# End-to-end against Redis
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_shared_dlq_channel_end_to_end():
    """Two failing handlers on two channels → one DLQ stream → one sink."""
    redis_client = redis.Redis(host="localhost", port=6379, decode_responses=False)
    test_id = uuid.uuid4().hex[:8]

    transport = RedisTransport()
    producers = Agent(f"prod-{test_id}", transport=transport)
    orders = Channel(f"orders-{test_id}", transport=transport)
    payments = Channel(f"payments-{test_id}", transport=transport)
    dlq_topic = f"dlq-{test_id}"
    dlq = Channel(dlq_topic, transport=transport)

    retry_opts = {
        "retry_on_idle_ms": 300,
        "retry_reclaim_interval_s": 0.5,
        "max_retries": 1,
    }

    @producers.subscribe(channel=orders, dlq_channel=dlq, **retry_opts)
    async def fail_orders(message):
        raise RuntimeError("orders always fail")

    @producers.subscribe(channel=payments, dlq_channel=dlq_topic, **retry_opts)
    async def fail_payments(message):
        raise RuntimeError("payments always fail")

    await producers.start()
    await orders.publish({"type": "order", "data": {"id": 1}})
    await payments.publish({"type": "payment", "data": {"id": 2}})

    for _ in range(60):
        await asyncio.sleep(0.5)
        if await redis_client.xlen(dlq.get_name()) >= 2:
            break
    assert await redis_client.xlen(dlq.get_name()) == 2, (
        "both failures land in ONE stream"
    )
    # The per-handler DLQ keys are never created when dlq_channel is set.
    assert not await redis_client.exists(
        f"{orders.get_name()}.prod-{test_id}-fail_orders-1.dlq"
    )
    assert not await redis_client.exists(
        f"{payments.get_name()}.prod-{test_id}-fail_payments-1.dlq"
    )

    # A sink that boots AFTER the failures happened: group_start="0" picks up
    # the backlog, and the body says where each entry came from.
    received: dict[str, dict] = {}
    got_both = asyncio.Event()
    sink_transport = RedisTransport()
    sink = Agent(f"sink-{test_id}", transport=sink_transport)

    @sink.subscribe(
        channel=Channel(dlq_topic, transport=sink_transport), group_start="0"
    )
    async def on_dead_letter(message):
        received[message["_dlq_source"]] = message
        if len(received) == 2:
            got_both.set()

    await sink.start()
    try:
        await asyncio.wait_for(got_both.wait(), timeout=15)
    finally:
        await sink.stop()
        await producers.stop()
        await redis_client.aclose()

    o = received[orders.get_name()]
    assert o["type"] == "order" and o["data"] == {"id": 1}
    assert o["_dlq_handler"] == f"prod-{test_id}-fail_orders-1"
    assert o["_dlq_reason"] == "max_retries"
    assert o["_dlq_retries"] == "1"  # max_retries=1 → one retry actually ran
    assert o["_retry_count"] == "0"  # fresh budget for the sink
    assert "_dlq_at" in o and "_original_message_id" in o

    p = received[payments.get_name()]
    assert p["type"] == "payment" and p["data"] == {"id": 2}
    assert p["_dlq_handler"] == f"prod-{test_id}-fail_payments-1"


@pytest.mark.asyncio
async def test_reclaimer_wraps_poison_entry_into_dlq():
    """An unparseable envelope is dead-lettered as a decodable JSON object."""
    redis_client = redis.Redis(host="localhost", port=6379, decode_responses=False)
    test_id = uuid.uuid4().hex[:8]
    stream = f"eggai.poison-{test_id}"
    group = "svc-h-1"
    dlq_stream = f"eggai.dlq-{test_id}"

    await redis_client.xgroup_create(stream, group, id="0", mkstream=True)
    raw = b"\x00\x01definitely-not-an-envelope"
    msg_id = await redis_client.xadd(stream, {b"__data__": raw})
    # A non-eggai producer's entry with no __data__ field at all.
    no_data_id = await redis_client.xadd(stream, {b"foo": b"bar"})
    # Deliver to a consumer and never ack → sits in the PEL like a crashed handler.
    await redis_client.xreadgroup(group, "worker", {stream: ">"}, count=2)
    await asyncio.sleep(0.05)

    manager = PendingReclaimerManager("redis://localhost:6379")
    config = ReclaimerConfig(
        stream=stream,
        group=group,
        consumer=f"{group}-reclaimer",
        retry_stream=f"{stream}.{group}.retry",
        min_idle_ms=10,
        interval_s=60.0,  # never fires on its own during the test
        max_retries=1,
        dlq_stream=dlq_stream,
        source_stream=stream,
        handler=group,
    )
    manager.add(config)
    await manager.start()
    try:
        await manager._reclaim_once(config)
    finally:
        await manager.stop()

    entries = await redis_client.xrange(dlq_stream)
    assert len(entries) == 2
    bodies = {}
    for _id, fields in entries:
        body_bytes, headers = BinaryMessageFormatV1.parse(fields[b"__data__"])
        assert headers == {}
        body = json.loads(body_bytes)
        bodies[body["_original_message_id"]] = body
    body = bodies[msg_id.decode()]
    assert body["_dlq_reason"] == "poison"
    assert body["_dlq_source"] == stream
    assert body["_dlq_handler"] == group
    assert body["_retry_count"] == "0"
    assert body["_dlq_retries"] == "0"
    assert base64.b64decode(body["_dlq_raw_b64"]) == raw
    # The __data__-less entry is wrapped too, instead of looping through retry.
    other = bodies[no_data_id.decode()]
    assert other["_dlq_reason"] == "poison"
    assert json.loads(base64.b64decode(other["_dlq_raw_b64"])) == {"foo": "bar"}

    pending = await redis_client.xpending(stream, group)
    assert pending["pending"] == 0, "original entry was acked"
    assert not await redis_client.exists(config.retry_stream), "poison never retried"
    await redis_client.aclose()
