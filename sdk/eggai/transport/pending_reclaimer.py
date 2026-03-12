import asyncio
import json
import logging
from collections.abc import Callable
from dataclasses import dataclass
from struct import pack
from typing import Any

import redis.asyncio as aioredis
from faststream.redis.parser.binary import BinaryMessageFormatV1

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
    retry_stream: str  # where to XADD rescued messages — never == stream
    min_idle_ms: int
    interval_s: float
    max_retries: int | None = None  # None = unlimited retries (no DLQ)
    dlq_stream: str | None = None  # e.g. "eggai.orders.dlq"
    on_dlq: Callable | None = None  # async or sync callback(fields, msg_id, count)


def _inject_retry_metadata(data: bytes, msg_id_str: str) -> tuple[bytes, int]:
    """
    Inject _retry_count and _original_message_id into a FastStream binary stream
    entry's JSON body so the handler can read them for idempotency checks.

    FastStream BinaryMessageFormatV1 layout:
      [8B magic][2B version=1][4B headers_start][4B data_start]
      [2B num_headers]([2B key_len][key][2B val_len][val])*
      [JSON body bytes]

    Returns a tuple of (modified __data__ bytes, new retry count).
    On parse failure returns (original data, 0) so the message is never
    mistakenly routed to the DLQ.
    """
    try:
        body_bytes, headers = BinaryMessageFormatV1.parse(data)
        body_dict = json.loads(body_bytes)
    except Exception:
        logger.warning(
            "Failed to inject retry metadata for message %s; passing through unchanged",
            msg_id_str,
            exc_info=True,
        )
        return data, 0

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
    return writer.get_bytes(), new_count


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

    def add(self, config: ReclaimerConfig) -> None:
        key = (config.stream, config.group, config.consumer)
        self._configs[key] = config

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
            except Exception:
                logger.exception(
                    "Reclaimer error — stream=%s group=%s", config.stream, config.group
                )

    async def _reclaim_once(self, config: ReclaimerConfig) -> None:
        # --- Paginated XPENDING scan ---
        # A fixed count=100 only scans one page; with large or high-traffic PELs,
        # stale entries outside the first page would be delayed indefinitely.
        stale_ids: list[Any] = []
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
                    stale_ids.append(entry["message_id"])
            if len(page) < 100:
                break  # last page
            # Exclusive lower bound for next page — decode bytes to str if needed.
            last_id = page[-1]["message_id"]
            cursor = "(" + (last_id.decode() if isinstance(last_id, bytes) else last_id)

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
            if data_key in fields:
                fields[data_key], new_count = _inject_retry_metadata(
                    fields[data_key], msg_id_str
                )

            # Route to DLQ if max retries exceeded, otherwise to retry stream.
            if (
                config.max_retries is not None
                and config.dlq_stream is not None
                and new_count > config.max_retries
            ):
                await self._redis_client.xadd(config.dlq_stream, fields)
                await self._redis_client.xack(config.stream, config.group, msg_id)
                logger.warning(
                    "Message %s exceeded max_retries=%d; moved to DLQ %s",
                    msg_id_str,
                    config.max_retries,
                    config.dlq_stream,
                )
                if config.on_dlq is not None:
                    try:
                        # Parse the binary envelope so the callback receives a
                        # plain dict instead of raw bytes.
                        parsed_msg: dict | bytes = fields
                        if data_key in fields:
                            try:
                                body_bytes, _ = BinaryMessageFormatV1.parse(
                                    fields[data_key]
                                )
                                parsed_msg = json.loads(body_bytes)
                            except Exception:
                                parsed_msg = fields
                        result = config.on_dlq(parsed_msg, msg_id_str, new_count)
                        if asyncio.iscoroutine(result):
                            await result
                    except Exception:
                        logger.exception(
                            "on_dlq callback failed for message %s", msg_id_str
                        )
            else:
                await self._redis_client.xadd(config.retry_stream, fields)
                await self._redis_client.xack(config.stream, config.group, msg_id)
                logger.debug("Reclaimed %s → %s", msg_id_str, config.retry_stream)
