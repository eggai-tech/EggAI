import asyncio
import base64
import datetime
import json
import logging
import random
from collections.abc import Callable
from dataclasses import dataclass
from struct import pack
from typing import Any

import redis.asyncio as aioredis
from faststream.redis.parser.binary import BinaryMessageFormatV1
from redis.exceptions import ResponseError

logger = logging.getLogger(__name__)


class _BinaryWriter:
    """Minimal binary writer for rebuilding FastStream BinaryMessageFormatV1 envelopes.

    Replaces the private ``faststream.redis.parser.binary.BinaryWriter`` so we
    don't depend on an unexported internal class.
    """

    def __init__(self) -> None:
        self.data = bytearray()

    def write(self, data: bytes) -> None:
        self.data.extend(data)

    def write_short(self, number: int) -> None:
        self.write(pack(">H", number))

    def write_int(self, number: int) -> None:
        self.write(pack(">I", number))

    def write_string(self, data: str | bytes) -> None:
        raw = data.encode() if isinstance(data, str) else data
        self.write_short(len(raw))
        self.write(raw)

    def get_bytes(self) -> bytes:
        return bytes(self.data)


@dataclass(frozen=True)
class ReclaimerConfig:
    stream: str  # full Redis key as given by Channel, e.g. "<namespace>.orders"
    group: str  # consumer group name (mirrors handler_id)
    consumer: str  # distinct from live consumer: f"{handler_id}-reclaimer"
    retry_stream: str  # full Redis key for reclaimed messages; equals `stream` for the retry reclaimer
    min_idle_ms: int
    interval_s: float
    max_retries: int | None = None  # None = unlimited retries (no DLQ)
    dlq_stream: str | None = (
        None  # full key, e.g. "<namespace>.orders.order-service-handle_order-1.dlq"
    )
    on_dlq: Callable | None = None  # async or sync callback(body, msg_id, retry_count)
    max_len: int | None = (
        None  # cap retry stream length (XADD MAXLEN ~); None = unbounded
    )
    # Cap for the DLQ stream, kept separate from `max_len` on purpose: MAXLEN trims
    # the whole stream regardless of who wrote an entry or whether it was consumed,
    # so on a *shared* DLQ (`dlq_channel`) every writer's cap would apply to every
    # other writer's dead letters. The transport therefore passes None for a shared
    # DLQ (retention is the sink's job) and `retry_max_len` for the per-handler one.
    dlq_max_len: int | None = None
    # Exponential backoff between retry attempts. The reclaimer treats a PEL entry
    # as "stale" once it has been idle for `min_idle_ms * (backoff_multiplier **
    # retry_count)` (capped at backoff_max_ms). multiplier=1.0 reproduces the
    # original constant cadence (stale at exactly min_idle_ms regardless of count).
    backoff_multiplier: float = 1.0  # 1.0 = constant cadence (no escalation)
    backoff_max_ms: int | None = None  # cap on the escalated threshold; None = uncapped
    backoff_jitter: float = 0.0  # fraction in [0,1]; adds up to this share on top of the threshold at random
    # Provenance recorded on every DLQ entry (see _dlq_metadata). `source_stream`
    # is the channel the handler subscribed to — NOT `stream`, which for the retry
    # reclaimer is the retry stream. `handler` is the handler suffix / consumer
    # group. Both matter once several handlers share one DLQ stream
    # (`dlq_channel`): the entry itself must say where it came from, because the
    # stream key no longer does.
    source_stream: str | None = None
    handler: str | None = None


def _encode_envelope(headers: dict, body_bytes: bytes) -> bytes:
    """Build a FastStream BinaryMessageFormatV1 envelope from headers + JSON body.

    Layout (mirrors ``BinaryMessageFormatV1.encode()``):
      [8B magic][2B version=1][4B headers_start][4B data_start]
      [2B num_headers]([2B key_len][key][2B val_len][val])*
      [body bytes]
    """
    headers_writer = _BinaryWriter()
    for key, value in headers.items():
        headers_writer.write_string(key)
        headers_writer.write_string(value)
    headers_bytes = headers_writer.get_bytes()

    writer = _BinaryWriter()
    writer.write(BinaryMessageFormatV1.IDENTITY_HEADER)  # 8 bytes → len=8
    writer.write_short(1)  # version=1, 2B → len=10
    headers_start = len(writer.data) + 8  # 10+8 = 18
    data_start = 2 + headers_start + len(headers_bytes)  # 2+18+headers_len
    writer.write_int(headers_start)  # 4B → len=14
    writer.write_int(data_start)  # 4B → len=18
    writer.write_short(len(headers))  # 2B → len=20
    writer.write(headers_bytes)
    writer.write(body_bytes)
    return writer.get_bytes()


def _dlq_metadata(config: ReclaimerConfig, reason: str) -> dict[str, str]:
    """Provenance keys added to a DLQ entry's JSON body.

    Kept as string values, like ``_retry_count``, so they survive any consumer
    that stringifies fields. ``reason`` is ``"max_retries"`` or ``"poison"``.
    """
    meta = {
        "_dlq_reason": reason,
        "_dlq_at": datetime.datetime.now(datetime.timezone.utc).isoformat(
            timespec="milliseconds"
        ),
    }
    if config.source_stream is not None:
        meta["_dlq_source"] = config.source_stream
    if config.handler is not None:
        meta["_dlq_handler"] = config.handler
    return meta


def _parse_entry(data: bytes) -> tuple[dict, dict, int] | None:
    """Parse a FastStream envelope into ``(headers, body, retry_count)``.

    Returns ``None`` for anything the reclaimer cannot safely re-queue: bytes
    that are not an envelope, a body that is not a JSON object, or a
    ``_retry_count`` that is not an integer. Such an entry is *poison* — its
    count can never be incremented, so re-queueing it would livelock the retry
    stream — and the caller dead-letters it instead of retrying.
    """
    try:
        body_bytes, headers = BinaryMessageFormatV1.parse(data)
        body = json.loads(body_bytes)
        if not isinstance(body, dict):
            raise TypeError(f"body is {type(body).__name__}, not a JSON object")
        retry_count = int(body.get("_retry_count", "0"))
    except Exception:
        return None
    return headers, body, retry_count


def _encode_body(headers: dict, body: dict) -> bytes:
    """Serialise ``body`` compactly and wrap it in an envelope with ``headers``."""
    return _encode_envelope(headers, json.dumps(body, separators=(",", ":")).encode())


def _inject_retry_metadata(
    data: bytes, msg_id_str: str
) -> tuple[dict, dict, int] | None:
    """Parse an entry and bump its retry metadata in the body dict.

    Returns ``(headers, body, new_count)`` with ``body["_retry_count"]``
    incremented and ``_original_message_id`` set if absent, so the handler can
    use them for idempotency checks. Returns ``None`` (after a warning) for a
    poison entry — see :func:`_parse_entry`. The caller encodes the body exactly
    once, after deciding whether it goes to the retry stream or the DLQ.
    """
    parsed = _parse_entry(data)
    if parsed is None:
        logger.warning(
            "Failed to inject retry metadata for message %s; treating as poison",
            msg_id_str,
        )
        return None
    headers, body, retry_count = parsed
    new_count = retry_count + 1
    body["_retry_count"] = str(new_count)
    body.setdefault("_original_message_id", msg_id_str)
    return headers, body, new_count


def _stamp_dead_letter(body: dict, meta: dict[str, str], retries: int) -> None:
    """Turn a message body into a DLQ entry body, in place.

    A DLQ entry is two things at once: the record of a finished retry history,
    and — once something subscribes to the DLQ — a *first* delivery to a new
    consumer. Hence:

    - origin keys (``_dlq_source``, ``_dlq_handler``, ``_dlq_at``) are written
      set-if-absent: if the message is dead-lettered a second time (the DLQ
      consumer itself gave up), they keep saying where it *originally* failed;
    - hop keys (``_dlq_reason``, ``_dlq_retries``) are overwritten on every
      dead-lettering: they say why the entry is in *this* DLQ, which is what its
      reader needs (the origin is still in the keys above);
    - ``_retry_count`` is reset to ``"0"``, so a DLQ consumer with its own
      ``retry_on_idle_ms`` starts with a fresh budget instead of inheriting an
      already-exceeded one (which would dead-letter it again on its first
      failure and, with backoff, make its first reclaim wait
      ``base * multiplier ** exhausted``).

    Metadata lives in the *body*, not in extra XADD fields: FastStream's decoder
    reads only ``__data__``, so body keys are all a DLQ subscriber can see.
    """
    for key in ("_dlq_source", "_dlq_handler", "_dlq_at"):
        if key in meta:
            body.setdefault(key, meta[key])  # first dead-lettering wins
    body["_dlq_reason"] = meta["_dlq_reason"]  # latest hop wins
    body["_dlq_retries"] = str(retries)
    body["_retry_count"] = "0"


def _poison_body(
    data: bytes, meta: dict[str, str], msg_id_str: str
) -> tuple[dict, dict]:
    """Build ``(headers, body)`` for a poison entry from its raw ``__data__``.

    A poison entry copied verbatim would reach a DLQ subscriber as raw bytes
    (FastStream's parser falls back to the bare payload), which a typed
    subscription silently skips and an untyped one cannot use. Instead the DLQ
    entry is a fresh, well-formed envelope whose body carries the provenance, a
    zero retry budget, and the original bytes base64-encoded as ``_dlq_raw_b64``
    for forensics and re-drive. Envelope headers (correlation id, traceparent…)
    are kept when the envelope itself parsed and only its body was unusable.
    """
    try:
        _, headers = BinaryMessageFormatV1.parse(data)
    except Exception:
        headers = {}
    body: dict = {
        "_original_message_id": msg_id_str,
        "_dlq_raw_b64": base64.b64encode(data).decode("ascii"),
    }
    _stamp_dead_letter(body, meta, 0)
    return headers, body


def _fields_as_json(fields: dict) -> bytes:
    """Render a stream entry that has no ``__data__`` field as JSON bytes.

    Such entries can only come from a non-eggai producer; they are wrapped as
    poison so they reach the DLQ instead of ping-ponging through the retry
    stream forever (their retry count can never be incremented).
    """

    def _text(value: Any) -> Any:
        return (
            value.decode("utf-8", errors="replace")
            if isinstance(value, bytes)
            else value
        )

    return json.dumps({_text(k): _text(v) for k, v in fields.items()}).encode()


class PendingReclaimerManager:
    """
    Manages background tasks that rescue stuck messages from the Redis Streams
    Pending Entries List (PEL).

    When a handler raises with NACK_ON_ERROR the message stays in the PEL
    indefinitely because FastStream only reads with XREADGROUP … > (new messages).
    Each reclaim loop:
      1. Pages through XPENDING to find entries idle longer than min_idle_ms.
      2. XCLAIM them under a dedicated reclaimer consumer.
      3. XADD the fields to retry_stream (a separate stream — avoids duplicates).
      4. XACK the original PEL entry.

    Delivery guarantee: at-least-once. XADD and XACK are not atomic; a crash
    between them will re-deliver the message on the next reclaim cycle.
    Handlers must be idempotent. The injected _original_message_id field (in the
    message body) can be used for application-level deduplication.
    """

    def __init__(self, redis_url: str, connection_kwargs: dict[str, Any] | None = None):
        self._redis_url = redis_url
        # Connection-resilience settings (socket_timeout, socket_keepalive,
        # health_check_interval, retry_on_timeout, …) forwarded from the
        # transport so this independent client recovers from a silently dropped
        # connection the same way the broker does. Without them a blocking read
        # against a half-dead socket (e.g. cloud Redis failover) hangs forever
        # with no socket timeout to break it.
        self._connection_kwargs: dict[str, Any] = connection_kwargs or {}
        self._redis_client: aioredis.Redis | None = None
        self._configs: dict[tuple[str, str, str], ReclaimerConfig] = {}
        self._tasks: dict[tuple[str, str, str], asyncio.Task] = {}
        self._running = False

    @property
    def _client(self) -> aioredis.Redis:
        """The connected Redis client; raises if accessed before start()."""
        client = self._redis_client
        if client is None:
            raise RuntimeError(
                "PendingReclaimerManager used before start(); no Redis client."
            )
        return client

    def add(self, config: ReclaimerConfig) -> tuple[str, str, str]:
        key = (config.stream, config.group, config.consumer)
        self._configs[key] = config
        return key

    def discard(self, key: tuple[str, str, str]) -> None:
        """Remove a registered config by key — used to roll back a partial subscribe."""
        self._configs.pop(key, None)

    async def start(self) -> None:
        """Start one background task per registered config. Safe to call again after stop."""
        # decode_responses=False: field values are kept as raw bytes so that
        # FastStream's binary-encoded __data__ field is passed through unchanged.
        # decode_responses is pinned here and must not be overridden by callers.
        self._redis_client = aioredis.from_url(
            self._redis_url,
            **{**self._connection_kwargs, "decode_responses": False},
        )
        self._running = True
        for key, config in self._configs.items():
            if key in self._tasks and not self._tasks[key].done():
                continue
            self._tasks[key] = asyncio.create_task(
                self._run(config), name=f"reclaimer:{config.stream}:{config.group}"
            )

    async def stop(self) -> None:
        """Cancel all reclaimer tasks and close the Redis connection."""
        self._running = False
        for task in self._tasks.values():
            task.cancel()
        await asyncio.gather(*self._tasks.values(), return_exceptions=True)
        self._tasks.clear()
        if self._redis_client is not None:
            await self._client.aclose()
            self._redis_client = None

    async def _run(self, config: ReclaimerConfig) -> None:
        # The flag, not just cancellation, ends the loop: redis-py >= 8 sends every
        # command through asyncio.wait_for, which on CPython < 3.12 can swallow the
        # CancelledError, so a cancelled reclaim may return normally.
        while self._running:
            # Sleep first so the broker has settled before the first scan.
            await asyncio.sleep(config.interval_s)
            try:
                await self._reclaim_once(config)
            except asyncio.CancelledError:
                raise
            except ResponseError as e:
                if "NOGROUP" in str(e):
                    await self._ensure_group(config)
                else:
                    logger.exception(
                        "Reclaimer error — stream=%s group=%s",
                        config.stream,
                        config.group,
                    )
            except Exception:
                logger.exception(
                    "Reclaimer error — stream=%s group=%s", config.stream, config.group
                )

    async def _ensure_group(self, config: ReclaimerConfig) -> None:
        """Recreate a consumer group after a NOGROUP error (e.g. Redis restart).

        Uses id="0" when the stream still has entries (partial group loss) so
        unprocessed messages are redelivered.  Falls back to id="$" with
        MKSTREAM when the stream itself is gone.
        """
        try:
            stream_exists = await self._client.exists(config.stream)
            create_id = "0" if stream_exists else "$"
            await self._client.xgroup_create(
                name=config.stream,
                groupname=config.group,
                id=create_id,
                mkstream=True,
            )
            logger.info(
                "Recreated consumer group %s on stream %s after NOGROUP error",
                config.group,
                config.stream,
            )
        except ResponseError as e:
            if "BUSYGROUP" not in str(e):
                raise

    async def _xadd(self, stream: str, fields: dict, max_len: int | None) -> None:
        """XADD with optional approximate length capping.

        ``approximate=True`` (the ``MAXLEN ~`` form) lets Redis trim on whole-node
        boundaries, which is far cheaper than exact trimming and is the
        recommended production setting. ``max_len=None`` means no trimming.
        """
        if max_len is not None:
            await self._client.xadd(stream, fields, maxlen=max_len, approximate=True)
        else:
            await self._client.xadd(stream, fields)

    def _effective_idle_ms(self, config: ReclaimerConfig, retry_count: int) -> float:
        """Idle time a message must accrue before this reclaim cycle treats it as stale.

        With backoff_multiplier=1.0 this is just min_idle_ms (the original constant
        cadence). Otherwise it grows geometrically with the message's retry count —
        30s, 60s, 120s, … for multiplier=2 — so a repeatedly-failing message is
        retried progressively less often, giving an overloaded downstream room to
        recover instead of being hammered on a fixed clock. backoff_max_ms caps the
        escalation.

        backoff_jitter spreads a cohort of messages that failed together so they
        don't all come due in the same instant (thundering herd). It is applied
        *upward* — adding a random 0..jitter fraction on top of the threshold —
        rather than downward, because min_idle_ms / retry_on_idle_ms is a hard floor:
        the reclaim scan and XCLAIM both refuse to touch a PEL entry idle for less
        than min_idle_ms (it may merely be slow, not stuck), so jitter that dipped
        below the base would be invisible. Spreading upward keeps every reclaim at or
        after the visibility timeout while still decorrelating the cohort. NOTE: the
        spread is only effective once jitter * threshold is comparable to the scan
        interval (retry_reclaim_interval_s, default 15s); smaller jitter is quantised
        away by the scan cadence, which matters mostly at the lowest backoff levels.
        """
        # A large retry_count can make multiplier**retry_count exceed the max float
        # and raise OverflowError. That's only realistically reachable when a cap is
        # set (the cap bounds the interval, so retry_count climbs linearly over days
        # for a never-acked poison message); uncapped, the interval grows so fast the
        # count can't physically get there. Treat overflow as "infinitely far away"
        # (+inf): with a cap, min() below clamps it to backoff_max_ms; uncapped, the
        # entry simply isn't due this cycle. Either way the reclaimer never dies — an
        # unguarded OverflowError here would abort the whole cycle and starve every
        # other message on the stream.
        try:
            threshold = config.min_idle_ms * (config.backoff_multiplier**retry_count)
        except OverflowError:
            threshold = float("inf")
        # Jitter before the cap so backoff_max_ms stays a hard ceiling on the result.
        if config.backoff_jitter > 0.0 and threshold != float("inf"):
            threshold *= 1.0 + random.uniform(0.0, config.backoff_jitter)
        if config.backoff_max_ms is not None:
            threshold = min(threshold, float(config.backoff_max_ms))
        return threshold

    async def _read_retry_count(self, stream: str, msg_id: Any) -> int:
        """Read a pending entry's current ``_retry_count`` without disturbing it.

        Uses XRANGE (non-destructive: unlike XCLAIM it neither resets the idle
        timer nor transfers PEL ownership) so we can decide whether a message's
        escalated backoff threshold has elapsed *before* committing to claim it.
        Any failure (missing entry, unparseable envelope) falls back to 0 so the
        message is treated with the base threshold rather than being skipped
        forever.
        """
        try:
            entries: Any = await self._client.xrange(stream, min=msg_id, max=msg_id)
            if not entries:
                return 0
            _id, fields = entries[0]
            data = fields.get(b"__data__")
            if data is None:
                return 0
            parsed = _parse_entry(data)
            return parsed[2] if parsed is not None else 0
        except Exception:
            return 0

    async def _reclaim_once(self, config: ReclaimerConfig) -> None:
        # --- Paginated XPENDING scan ---
        # A fixed count=100 only scans one page; with large or high-traffic PELs,
        # stale entries outside the first page would be delayed indefinitely.
        #
        # min_idle_ms is the *minimum* possible threshold (retry_count=0), so it
        # works as a cheap pre-filter here regardless of backoff settings: anything
        # below it can't be due yet under any retry count. When backoff is active we
        # refine the survivors below with their per-message escalated threshold.
        candidates: list[tuple[Any, int]] = []  # (message_id, idle_ms)
        cursor = "-"
        while True:
            page: list[dict] = await self._client.xpending_range(
                name=config.stream,
                groupname=config.group,
                min=cursor,
                max="+",
                count=100,
            )
            if not page:
                break
            for entry in page:
                idle = entry.get("time_since_delivered", 0)
                if idle >= config.min_idle_ms:
                    candidates.append((entry["message_id"], idle))
            if len(page) < 100:
                break  # last page
            # Exclusive lower bound for next page — decode bytes to str if needed.
            last_id = page[-1]["message_id"]
            cursor = "(" + (last_id.decode() if isinstance(last_id, bytes) else last_id)

        if not candidates:
            return

        # Fast path: constant cadence (no escalation, no jitter) keeps the original
        # behaviour and skips the extra per-message XRANGE reads entirely.
        backoff_active = config.backoff_multiplier != 1.0 or config.backoff_jitter > 0.0
        if not backoff_active:
            stale_ids: list[Any] = [msg_id for msg_id, _ in candidates]
        else:
            stale_ids = []
            for msg_id, idle in candidates:
                retry_count = await self._read_retry_count(config.stream, msg_id)
                if idle >= self._effective_idle_ms(config, retry_count):
                    stale_ids.append(msg_id)
            # Messages not yet due stay in the PEL untouched; their idle keeps
            # growing and a later cycle reclaims them once the threshold passes.
            if not stale_ids:
                return

        claimed: Any = await self._client.xclaim(
            name=config.stream,
            groupname=config.group,
            consumername=config.consumer,  # "-reclaimer" suffix — no feedback loop
            min_idle_time=config.min_idle_ms,
            message_ids=stale_ids,
        )

        data_key = b"__data__"
        for msg_id, fields in claimed:
            msg_id_str = msg_id.decode() if isinstance(msg_id, bytes) else msg_id

            # Parse once and bump the retry metadata in the body dict; the body is
            # encoded exactly once below, after routing.
            # NOTE: XADD then XACK is not atomic. A crash here re-delivers on the
            # next cycle (at-least-once). Use _original_message_id to deduplicate.
            parsed = (
                _inject_retry_metadata(fields[data_key], msg_id_str)
                if data_key in fields
                else None
            )

            # Poison: no __data__ field, not an envelope, a non-object body, or a
            # non-integer _retry_count. Its count can never be incremented, so
            # re-queueing it would livelock the retry stream. Route it to the DLQ
            # (wrapped so it decodes) if configured, otherwise drop it (XACK) with
            # a loud error rather than spin on it indefinitely.
            if parsed is None:
                if config.dlq_stream is not None:
                    raw = (
                        fields[data_key]
                        if data_key in fields
                        else _fields_as_json(fields)
                    )
                    headers, body = _poison_body(
                        raw, _dlq_metadata(config, "poison"), msg_id_str
                    )
                    dlq_fields = dict(fields)
                    dlq_fields[data_key] = _encode_body(headers, body)
                    await self._xadd(config.dlq_stream, dlq_fields, config.dlq_max_len)
                    await self._client.xack(config.stream, config.group, msg_id)
                    logger.warning(
                        "Message %s has an unparseable envelope; moved to DLQ %s "
                        "(retry count cannot be tracked)",
                        msg_id_str,
                        config.dlq_stream,
                    )
                    await self._invoke_on_dlq(config, body, msg_id_str, 0)
                else:
                    await self._client.xack(config.stream, config.group, msg_id)
                    logger.error(
                        "Message %s has an unparseable envelope and no DLQ is "
                        "configured; dropping it to avoid a retry-stream livelock",
                        msg_id_str,
                    )
                continue

            headers, body, new_count = parsed

            # Route to DLQ if max retries exceeded, otherwise to retry stream.
            if (
                config.max_retries is not None
                and config.dlq_stream is not None
                and new_count > config.max_retries
            ):
                # new_count is the retry that would have run next; the retries
                # that actually ran are new_count - 1 (== max_retries).
                _stamp_dead_letter(
                    body, _dlq_metadata(config, "max_retries"), new_count - 1
                )
                dlq_fields = dict(fields)
                dlq_fields[data_key] = _encode_body(headers, body)
                await self._xadd(config.dlq_stream, dlq_fields, config.dlq_max_len)
                await self._client.xack(config.stream, config.group, msg_id)
                logger.warning(
                    "Message %s exceeded max_retries=%d; moved to DLQ %s",
                    msg_id_str,
                    config.max_retries,
                    config.dlq_stream,
                )
                await self._invoke_on_dlq(config, body, msg_id_str, new_count)
            else:
                fields[data_key] = _encode_body(headers, body)
                await self._xadd(config.retry_stream, fields, config.max_len)
                await self._client.xack(config.stream, config.group, msg_id)
                logger.debug("Reclaimed %s → %s", msg_id_str, config.retry_stream)

    async def _invoke_on_dlq(
        self,
        config: ReclaimerConfig,
        body: dict,
        msg_id_str: str,
        retry_count: int,
    ) -> None:
        """Invoke the optional on_dlq callback with the DLQ entry's body dict.

        The dict is exactly what a subscriber on the DLQ stream receives: the
        payload plus ``_retry_count`` (reset to "0"), ``_dlq_retries``,
        ``_original_message_id`` and the ``_dlq_*`` provenance; for a poison
        entry the same metadata plus ``_dlq_raw_b64`` instead of a payload.
        Callback errors are logged but never block the DLQ write that already
        happened.
        """
        if config.on_dlq is None:
            return
        try:
            result = config.on_dlq(body, msg_id_str, retry_count)
            if asyncio.iscoroutine(result):
                await result
        except Exception:
            logger.exception("on_dlq callback failed for message %s", msg_id_str)
