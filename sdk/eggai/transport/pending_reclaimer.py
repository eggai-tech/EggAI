import asyncio
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
        self.write_short(len(data))
        self.write(data.encode() if isinstance(data, str) else data)

    def get_bytes(self) -> bytes:
        return bytes(self.data)


@dataclass(frozen=True)
class ReclaimerConfig:
    stream: str  # full Redis key, e.g. "eggai.orders"
    group: str  # consumer group name (mirrors handler_id)
    consumer: str  # distinct from live consumer: f"{handler_id}-reclaimer"
    retry_stream: str  # full Redis key for reclaimed messages; equals `stream` for the retry reclaimer
    min_idle_ms: int
    interval_s: float
    max_retries: int | None = None  # None = unlimited retries (no DLQ)
    dlq_stream: str | None = (
        None  # full key, e.g. "eggai.orders.order-service-handle_order-1.dlq"
    )
    on_dlq: Callable | None = None  # async or sync callback(fields, msg_id, count)
    max_len: int | None = (
        None  # cap retry/DLQ stream length (XADD MAXLEN ~); None = unbounded
    )
    # Exponential backoff between retry attempts. The reclaimer treats a PEL entry
    # as "stale" once it has been idle for `min_idle_ms * (backoff_multiplier **
    # retry_count)` (capped at backoff_max_ms). multiplier=1.0 reproduces the
    # original constant cadence (stale at exactly min_idle_ms regardless of count).
    backoff_multiplier: float = 1.0  # 1.0 = constant cadence (no escalation)
    backoff_max_ms: int | None = None  # cap on the escalated threshold; None = uncapped
    backoff_jitter: float = 0.0  # fraction in [0,1]; adds up to this share on top of the threshold at random


def _inject_retry_metadata(data: bytes, msg_id_str: str) -> tuple[bytes, int, bool]:
    """
    Inject _retry_count and _original_message_id into a FastStream binary stream
    entry's JSON body so the handler can read them for idempotency checks.

    FastStream BinaryMessageFormatV1 layout:
      [8B magic][2B version=1][4B headers_start][4B data_start]
      [2B num_headers]([2B key_len][key][2B val_len][val])*
      [JSON body bytes]

    Returns a tuple of (modified __data__ bytes, new retry count, parsed_ok).
    On parse failure returns (original data, 0, False): the caller treats an
    unparseable envelope as a poison message (its retry count can never be
    incremented, so re-queueing it would livelock the retry stream) and routes
    it to the DLQ or drops it instead.
    """
    try:
        body_bytes, headers = BinaryMessageFormatV1.parse(data)
        body_dict = json.loads(body_bytes)
    except Exception:
        logger.warning(
            "Failed to inject retry metadata for message %s; treating as poison",
            msg_id_str,
            exc_info=True,
        )
        return data, 0, False

    new_count = int(body_dict.get("_retry_count", "0")) + 1
    body_dict["_retry_count"] = str(new_count)
    body_dict.setdefault("_original_message_id", msg_id_str)
    new_body_bytes = json.dumps(body_dict, separators=(",", ":")).encode()

    # Re-encode headers section.
    headers_writer = _BinaryWriter()
    for key, value in headers.items():
        headers_writer.write_string(key)
        headers_writer.write_string(value)
    headers_bytes = headers_writer.get_bytes()

    # Rebuild the binary envelope — mirrors BinaryMessageFormatV1.encode().
    writer = _BinaryWriter()
    writer.write(BinaryMessageFormatV1.IDENTITY_HEADER)  # 8 bytes → len=8
    writer.write_short(1)  # version=1, 2B → len=10
    headers_start = len(writer.data) + 8  # 10+8 = 18
    data_start = 2 + headers_start + len(headers_bytes)  # 2+18+headers_len
    writer.write_int(headers_start)  # 4B → len=14
    writer.write_int(data_start)  # 4B → len=18
    writer.write_short(len(headers))  # 2B → len=20
    writer.write(headers_bytes)
    writer.write(new_body_bytes)
    return writer.get_bytes(), new_count, True


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

    def __init__(self, redis_url: str):
        self._redis_url = redis_url
        self._redis_client: aioredis.Redis | None = None
        self._configs: dict[tuple[str, str, str], ReclaimerConfig] = {}
        self._tasks: dict[tuple[str, str, str], asyncio.Task] = {}

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
        self._redis_client = aioredis.from_url(self._redis_url, decode_responses=False)
        for key, config in self._configs.items():
            if key in self._tasks and not self._tasks[key].done():
                continue
            self._tasks[key] = asyncio.create_task(
                self._run(config), name=f"reclaimer:{config.stream}:{config.group}"
            )

    async def stop(self) -> None:
        """Cancel all reclaimer tasks and close the Redis connection."""
        for task in self._tasks.values():
            task.cancel()
        for task in self._tasks.values():
            try:
                await task
            except asyncio.CancelledError:
                pass
        self._tasks.clear()
        if self._redis_client is not None:
            await self._redis_client.aclose()
            self._redis_client = None

    async def _run(self, config: ReclaimerConfig) -> None:
        while True:
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
            stream_exists = await self._redis_client.exists(config.stream)
            create_id = "0" if stream_exists else "$"
            await self._redis_client.xgroup_create(
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
            await self._redis_client.xadd(
                stream, fields, maxlen=max_len, approximate=True
            )
        else:
            await self._redis_client.xadd(stream, fields)

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
            entries = await self._redis_client.xrange(stream, min=msg_id, max=msg_id)
            if not entries:
                return 0
            _id, fields = entries[0]
            data = fields.get(b"__data__")
            if data is None:
                return 0
            body_bytes, _headers = BinaryMessageFormatV1.parse(data)
            return int(json.loads(body_bytes).get("_retry_count", "0"))
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
            page: list[dict] = await self._redis_client.xpending_range(
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

        claimed: list[tuple[Any, dict]] = await self._redis_client.xclaim(
            name=config.stream,
            groupname=config.group,
            consumername=config.consumer,  # "-reclaimer" suffix — no feedback loop
            min_idle_time=config.min_idle_ms,
            message_ids=stale_ids,
        )

        for msg_id, fields in claimed:
            msg_id_str = msg_id.decode() if isinstance(msg_id, bytes) else msg_id

            # Inject retry metadata into the FastStream binary payload body so the
            # handler sees _retry_count and _original_message_id in the message dict.
            # NOTE: XADD then XACK is not atomic. A crash here re-delivers on the
            # next cycle (at-least-once). Use _original_message_id to deduplicate.
            data_key = b"__data__"
            new_count = 0
            parsed_ok = True
            if data_key in fields:
                fields[data_key], new_count, parsed_ok = _inject_retry_metadata(
                    fields[data_key], msg_id_str
                )

            # Poison message: a permanently-unparseable envelope can never have its
            # retry count incremented, so re-queueing it to the retry stream would
            # livelock forever. Route it to the DLQ if configured, otherwise drop it
            # (XACK) with a loud warning rather than spin on it indefinitely.
            if not parsed_ok:
                if config.dlq_stream is not None:
                    await self._xadd(config.dlq_stream, fields, config.max_len)
                    await self._redis_client.xack(config.stream, config.group, msg_id)
                    logger.warning(
                        "Message %s has an unparseable envelope; moved to DLQ %s "
                        "(retry count cannot be tracked)",
                        msg_id_str,
                        config.dlq_stream,
                    )
                    await self._invoke_on_dlq(
                        config, fields, data_key, msg_id_str, new_count
                    )
                else:
                    await self._redis_client.xack(config.stream, config.group, msg_id)
                    logger.error(
                        "Message %s has an unparseable envelope and no DLQ is "
                        "configured; dropping it to avoid a retry-stream livelock",
                        msg_id_str,
                    )
                continue

            # Route to DLQ if max retries exceeded, otherwise to retry stream.
            if (
                config.max_retries is not None
                and config.dlq_stream is not None
                and new_count > config.max_retries
            ):
                await self._xadd(config.dlq_stream, fields, config.max_len)
                await self._redis_client.xack(config.stream, config.group, msg_id)
                logger.warning(
                    "Message %s exceeded max_retries=%d; moved to DLQ %s",
                    msg_id_str,
                    config.max_retries,
                    config.dlq_stream,
                )
                await self._invoke_on_dlq(
                    config, fields, data_key, msg_id_str, new_count
                )
            else:
                await self._xadd(config.retry_stream, fields, config.max_len)
                await self._redis_client.xack(config.stream, config.group, msg_id)
                logger.debug("Reclaimed %s → %s", msg_id_str, config.retry_stream)

    async def _invoke_on_dlq(
        self,
        config: ReclaimerConfig,
        fields: dict,
        data_key: bytes,
        msg_id_str: str,
        new_count: int,
    ) -> None:
        """Invoke the optional on_dlq callback with a parsed message dict.

        Parses the binary envelope so the callback receives a plain dict instead
        of raw bytes; falls back to the raw fields if parsing fails. Callback
        errors are logged but never block the DLQ write that already happened.
        """
        if config.on_dlq is None:
            return
        try:
            parsed_msg: dict | bytes = fields
            if data_key in fields:
                try:
                    body_bytes, _ = BinaryMessageFormatV1.parse(fields[data_key])
                    parsed_msg = json.loads(body_bytes)
                except Exception:
                    parsed_msg = fields
            result = config.on_dlq(parsed_msg, msg_id_str, new_count)
            if asyncio.iscoroutine(result):
                await result
        except Exception:
            logger.exception("on_dlq callback failed for message %s", msg_id_str)
