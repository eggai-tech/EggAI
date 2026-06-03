"""Tests for distributed tracing / OpenTelemetry integration."""

from __future__ import annotations

import asyncio

import pytest

from eggai.schemas import BaseMessage
from eggai.transport import InMemoryTransport, eggai_set_default_transport


def test_traceparent_default_none():
    msg = BaseMessage(source="test", type="test.event")
    assert msg.traceparent is None


def test_traceparent_survives_json_round_trip():
    tp = "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"
    msg = BaseMessage(source="test", type="test.event", traceparent=tp)
    restored = BaseMessage.model_validate_json(msg.model_dump_json())
    assert restored.traceparent == tp


@pytest.mark.asyncio
async def test_noop_publish_and_subscribe_work_without_setup_tracing():
    import eggai.tracing as t

    original_backend = t._backend
    t._backend = None

    transport = InMemoryTransport()
    eggai_set_default_transport(transport)

    from eggai import Channel

    channel = Channel("tracing-noop-test", transport=transport)
    received = []

    async def handler(msg):
        received.append(msg)

    await channel.subscribe(handler)
    await transport.connect()
    await channel.publish(BaseMessage(source="test", type="test.noop"))

    await asyncio.sleep(0.05)
    assert len(received) == 1

    await transport.disconnect()
    InMemoryTransport._CHANNELS.clear()
    InMemoryTransport._SUBSCRIPTIONS.clear()
    t._backend = original_backend


# OTEL does not allow overriding the global TracerProvider, so a single shared
# provider + exporter is configured once at module level and cleared between tests.
otel = pytest.importorskip("opentelemetry")

from opentelemetry import trace as _otel_trace  # noqa: E402
from opentelemetry.sdk.trace import TracerProvider as _TracerProvider  # noqa: E402
from opentelemetry.sdk.trace.export import SimpleSpanProcessor  # noqa: E402
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (  # noqa: E402
    InMemorySpanExporter,
)

_SHARED_EXPORTER = InMemorySpanExporter()
_SHARED_PROVIDER = _TracerProvider()
_SHARED_PROVIDER.add_span_processor(SimpleSpanProcessor(_SHARED_EXPORTER))
_otel_trace.set_tracer_provider(_SHARED_PROVIDER)


def _activate_tracer():
    import eggai
    import eggai.tracing as t

    _SHARED_EXPORTER.clear()
    t._backend = t._OtelBackend(_otel_trace.get_tracer("eggai", eggai.__version__))


def _deactivate_tracer():
    import eggai.tracing as t

    t._backend = t._NoOpBackend()


@pytest.fixture()
def fresh_transport():
    transport = InMemoryTransport()
    eggai_set_default_transport(transport)
    yield transport
    InMemoryTransport._CHANNELS.clear()
    InMemoryTransport._SUBSCRIPTIONS.clear()


@pytest.mark.asyncio
async def test_span_publish_creates_producer_span(fresh_transport):
    _activate_tracer()
    try:
        from eggai import Channel

        ch = Channel("tracing-pub-test", transport=fresh_transport)
        await fresh_transport.connect()
        await ch.publish(BaseMessage(source="svc", type="test.pub"))

        spans = _SHARED_EXPORTER.get_finished_spans()
        assert len(spans) == 1
        span = spans[0]
        assert "eggai.publish" in span.name
        assert span.attributes.get("messaging.system") == "eggai"
        assert span.attributes.get("messaging.operation") == "publish"
    finally:
        await fresh_transport.disconnect()
        _deactivate_tracer()


@pytest.mark.asyncio
async def test_span_process_creates_consumer_span_with_same_trace_id(fresh_transport):
    _activate_tracer()
    try:
        from eggai import Channel

        ch = Channel("tracing-proc-test", transport=fresh_transport)

        async def handler(msg):
            pass

        await ch.subscribe(handler)
        await fresh_transport.connect()
        await ch.publish(BaseMessage(source="svc", type="test.proc"))
        await asyncio.sleep(0.1)

        spans = _SHARED_EXPORTER.get_finished_spans()
        span_names = [s.name for s in spans]
        assert any("eggai.publish" in n for n in span_names)
        assert any("eggai.process" in n for n in span_names)

        publish_span = next(s for s in spans if "eggai.publish" in s.name)
        process_span = next(s for s in spans if "eggai.process" in s.name)
        assert publish_span.context.trace_id == process_span.context.trace_id
    finally:
        await fresh_transport.disconnect()
        _deactivate_tracer()


@pytest.mark.asyncio
async def test_span_existing_traceparent_continues_the_trace(fresh_transport):
    _activate_tracer()
    try:
        from eggai import Channel

        external_tp = "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"
        external_trace_id = int("4bf92f3577b34da6a3ce929d0e0e4736", 16)

        ch = Channel("tracing-incoming-test", transport=fresh_transport)
        done = asyncio.Event()

        async def handler(msg):
            done.set()

        await ch.subscribe(handler)
        await fresh_transport.connect()
        await ch.publish(
            BaseMessage(source="svc", type="test.incoming", traceparent=external_tp)
        )

        await asyncio.wait_for(done.wait(), timeout=2.0)
        await asyncio.sleep(0.05)

        spans = _SHARED_EXPORTER.get_finished_spans()
        process_span = next((s for s in spans if "eggai.process" in s.name), None)
        assert process_span is not None
        assert process_span.context.trace_id == external_trace_id
    finally:
        await fresh_transport.disconnect()
        _deactivate_tracer()


@pytest.mark.asyncio
async def test_span_multi_hop_shares_single_trace_id(fresh_transport):
    _activate_tracer()
    try:
        from eggai import Channel

        ch_a = Channel("tracing-hop-a", transport=fresh_transport)
        ch_b = Channel("tracing-hop-b", transport=fresh_transport)
        done = asyncio.Event()

        async def handler_a(msg):
            tp = (
                msg.get("traceparent")
                if isinstance(msg, dict)
                else getattr(msg, "traceparent", None)
            )
            await ch_b.publish(
                BaseMessage(source="svc-a", type="test.hop.b", traceparent=tp)
            )

        async def handler_b(msg):
            done.set()

        await ch_a.subscribe(handler_a)
        await ch_b.subscribe(handler_b)
        await fresh_transport.connect()

        await ch_a.publish(BaseMessage(source="origin", type="test.hop.a"))

        await asyncio.wait_for(done.wait(), timeout=2.0)
        await asyncio.sleep(0.05)

        spans = _SHARED_EXPORTER.get_finished_spans()
        assert len(spans) >= 3

        trace_ids = {s.context.trace_id for s in spans}
        assert len(trace_ids) == 1, f"Expected single trace_id, got: {trace_ids}"
    finally:
        await fresh_transport.disconnect()
        _deactivate_tracer()
