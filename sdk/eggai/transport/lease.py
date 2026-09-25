"""In-flight lease renewal for Redis Streams consumer groups.

With SDK-managed retries (``retry_on_idle_ms``) the reclaimer treats every PEL
entry idle for longer than ``retry_on_idle_ms`` as abandoned. Redis only resets
an entry's idle time when it is (re)delivered, not while a handler works on it,
so a handler that runs longer than ``retry_on_idle_ms`` has its entry reclaimed
and redelivered while it is still running: the same message is processed twice,
in parallel.

``lease_renewal=True`` keeps the entries a subscription is working on "fresh":
every ``lease_renewal_interval_ms`` it runs, per entry and atomically (one Lua
script), ``XCLAIM <stream> <group> <consumer> 0 <id> JUSTID`` on entries this
consumer still owns. That resets the idle time without changing the owner or the
delivery count, so the reclaimer skips them. A consumer that crashed stops
renewing, and its entries are reclaimed ``retry_on_idle_ms`` after the last
renewal, as before.

Leased entries are the ones being handled plus the ones FastStream has already
read into this consumer's PEL but not handed to the handler yet (``max_records``
> 1, ``max_workers`` > 1): they are idle while queued in the process too.

``max_processing_ms`` is the matching deadline: a handler still running after it
is cancelled and its entry NACKed, so the normal retry path picks it up. Without
it, a hung handler would hold its lease forever.
"""

import asyncio
import functools
import logging
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from typing import Any

import redis.asyncio as aioredis

from eggai.transport.middleware_utils import call_handler, is_async_callable

logger = logging.getLogger(__name__)

# Subscribe options owned by this module (popped by RedisTransport.subscribe).
LEASE_OPTION_KEYS = (
    "lease_renewal",
    "lease_renewal_interval_ms",
    "cancel_on_lease_lost",
    "max_processing_ms",
)

# Ids per renewal script call: keeps each Lua run (3 cheap commands per id)
# short, so Redis is never blocked noticeably.
_CHUNK = 100
# XPENDING page size for the prefetch scan. The scan reads only this consumer's
# PEL from the oldest run in flight onwards, so one page covers it in practice;
# larger PELs are paged.
_SCAN_PAGE = 1000
# Shortest pause between two renewal rounds, as a share of the interval.
_MIN_PAUSE_RATIO = 0.1

# Per id: 1 = renewed, 0 = lost (not in this consumer's PEL: reclaimed, acked by
# someone else, or claimed by another consumer), 2 = trimmed (still ours in the
# PEL, but the entry was deleted from the stream, so nothing can redeliver it).
# Checked and claimed in one script so a reclaimer can't take the entry between
# the ownership check and the XCLAIM (a plain XCLAIM with min-idle-time 0 would
# steal it back from whoever holds it).
_RENEW_SCRIPT = """
local out = {}
for i = 3, #ARGV do
  local id = ARGV[i]
  local p = redis.call('XPENDING', KEYS[1], ARGV[1], id, id, 1)
  if #p == 0 or p[1][2] ~= ARGV[2] then
    out[#out + 1] = 0
  elseif #redis.call('XRANGE', KEYS[1], id, id) == 0 then
    out[#out + 1] = 2
  else
    redis.call('XCLAIM', KEYS[1], ARGV[1], ARGV[2], 0, id, 'JUSTID')
    out[#out + 1] = 1
  end
end
return out
"""
_LOST, _RENEWED, _TRIMMED = 0, 1, 2


class LeaseLostError(Exception):
    """A handler's stream entry left its consumer's PEL while it was running.

    Raised by a ``lease_renewal`` subscription (with the default
    ``cancel_on_lease_lost=True``) in place of the handler's result, after the
    handler was cancelled. The entry was reclaimed (usually after renewals kept
    failing for longer than ``retry_on_idle_ms``, e.g. during a Redis outage)
    and has been, or will be, redelivered; cancelling this run keeps it from
    running in parallel with that redelivery. Also raised, without running the
    handler, for an entry that was lost while it was still queued in the
    process. The entry is not acked: it is not this consumer's any more.

    A batch is one unit: if any of its entries is lost, the batch handler is
    cancelled and none is acked; the entries still owned stay pending and are
    retried. ``message_ids`` are all the run's entries, ``lost_ids`` the ones
    that left the PEL.
    """

    def __init__(
        self,
        stream: str,
        group: str,
        message_ids: Iterable[str],
        lost_ids: Iterable[str] | None = None,
    ):
        self.stream = stream
        self.group = group
        self.message_ids = tuple(message_ids)
        self.lost_ids = tuple(lost_ids) if lost_ids is not None else self.message_ids
        super().__init__(
            f"lease lost on stream {stream!r} group {group!r} for "
            f"{', '.join(self.lost_ids)}: the entry left this consumer's PEL "
            "(reclaimed for redelivery); the handler was cancelled"
            + (
                f" (batch of {', '.join(self.message_ids)})"
                if self.lost_ids != self.message_ids
                else ""
            )
        )


class ProcessingTimeoutError(TimeoutError):
    """A handler ran longer than its subscription's ``max_processing_ms``.

    The handler was cancelled and the entry is NACKed (left in the PEL), so the
    reclaimer retries it after ``retry_on_idle_ms``, counting towards
    ``max_retries`` like any other failure.
    """

    def __init__(
        self,
        stream: str,
        group: str,
        message_ids: Iterable[str],
        max_processing_ms: int,
    ):
        self.stream = stream
        self.group = group
        self.message_ids = tuple(message_ids)
        self.max_processing_ms = max_processing_ms
        super().__init__(
            f"handler exceeded max_processing_ms={max_processing_ms} on stream "
            f"{stream!r} group {group!r} for {', '.join(self.message_ids)}; "
            "cancelled, the entry is left for retry"
        )


@dataclass(frozen=True)
class LeaseOptions:
    """Validated lease-related subscribe options."""

    lease_renewal: bool = False
    interval_ms: int | None = None  # resolved: retry_on_idle_ms // 3 by default
    cancel_on_lease_lost: bool = True
    max_processing_ms: int | None = None


def _is_positive_int(value: Any) -> bool:
    # bool is an int subclass: True must not pass as 1 ms.
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def resolve_lease_options(
    options: Mapping[str, Any], retry_on_idle_ms: int | None
) -> LeaseOptions:
    """Validate the lease options in ``options`` (a subscribe kwargs mapping).

    Shared by ``Agent.subscribe`` (decoration time) and
    ``RedisTransport.subscribe``, so a bad combination fails the same way on
    both paths. ``retry_on_idle_ms`` is the subscription's reclaim threshold.
    ``options`` is only read, never modified.
    """
    lease = options.get("lease_renewal", False)
    interval_ms = options.get("lease_renewal_interval_ms")
    cancel_on_lost = options.get("cancel_on_lease_lost", True)
    max_processing_ms = options.get("max_processing_ms")
    if not isinstance(lease, bool):
        raise ValueError("lease_renewal must be True or False")
    if not isinstance(cancel_on_lost, bool):
        raise ValueError("cancel_on_lease_lost must be True or False")
    if not lease:
        if interval_ms is not None or "cancel_on_lease_lost" in options:
            raise ValueError(
                "lease_renewal_interval_ms / cancel_on_lease_lost require "
                "lease_renewal=True."
            )
    else:
        if retry_on_idle_ms is None:
            raise ValueError(
                "lease_renewal requires retry_on_idle_ms: the lease keeps the "
                "SDK-managed reclaimer from redelivering an entry that is still "
                "being processed, and without retry_on_idle_ms there is none."
            )
        if interval_ms is None:
            interval_ms = max(1, retry_on_idle_ms // 3)
        elif not _is_positive_int(interval_ms):
            raise ValueError("lease_renewal_interval_ms must be a positive int")
        elif interval_ms >= retry_on_idle_ms:
            raise ValueError(
                "lease_renewal_interval_ms must be < retry_on_idle_ms: an entry "
                "renewed less often than the reclaim threshold is reclaimed "
                "between two renewals (the default is retry_on_idle_ms // 3)."
            )
    if max_processing_ms is not None:
        if not _is_positive_int(max_processing_ms):
            raise ValueError("max_processing_ms must be a positive int")
        if retry_on_idle_ms is None:
            raise ValueError(
                "max_processing_ms requires retry_on_idle_ms: a handler past its "
                "deadline is NACKed, and only the SDK-managed reclaimer retries a "
                "NACKed entry."
            )
    return LeaseOptions(
        lease_renewal=lease,
        interval_ms=interval_ms if lease else None,
        cancel_on_lease_lost=cancel_on_lost,
        max_processing_ms=max_processing_ms,
    )


def _id_key(msg_id: str) -> tuple[int, int]:
    ms, _, seq = msg_id.partition("-")
    return int(ms), int(seq or 0)


def _text(value: Any) -> str:
    return value.decode() if isinstance(value, bytes) else str(value)


@dataclass(frozen=True)
class LeaseConfig:
    stream: str  # full stream key (main or .retry stream)
    group: str
    consumer: str  # the FastStream consumer name that owns the PEL entries
    interval_s: float
    cancel_on_lost: bool = True
    # Also renew entries read into this consumer's PEL but not yet handed to the
    # handler (max_records > 1 without batch, or max_workers > 1).
    scan_prefetched: bool = False

    @property
    def timeout_s(self) -> float:
        """Bound on each renewal round trip: half the interval, so a hung call
        never delays the next renewal by a whole interval."""
        return self.interval_s / 2


class _Invocation:
    """One handler run and the stream entries it covers (several in batch mode)."""

    __slots__ = ("ids", "task", "reason", "lost", "lost_ids")

    def __init__(self, ids: Iterable[str]):
        self.ids: tuple[str, ...] = tuple(ids)
        self.task: asyncio.Task | None = None
        # Why the SDK cancelled the run: "lease_lost" or "timeout".
        self.reason: str | None = None
        self.lost = False
        # The ids that left the PEL (a subset of ids in batch mode).
        self.lost_ids: list[str] = []

    def cancel(self, reason: str) -> None:
        if self.reason is None:
            self.reason = reason
        if self.task is not None and not self.task.done():
            self.task.cancel()


class LeaseKeeper:
    """Renews the in-flight entries of one (stream, group, consumer)."""

    def __init__(self, config: LeaseConfig):
        self.config = config
        self._in_flight: dict[str, _Invocation] = {}
        # Entries whose handler already finished in this process but may still be
        # in the PEL (a failure, NACKed for retry). Never renewed: the reclaimer
        # must see them go idle. Only needed while other runs are in flight.
        self._finished: set[str] = set()
        # Prefetched entries found lost before their handler started.
        self._lost_queued: set[str] = set()
        # Entries trimmed from the stream while in flight: no longer renewed.
        self._trimmed: set[str] = set()

    @property
    def in_flight(self) -> dict[str, _Invocation]:
        return self._in_flight

    def begin(self, ids: Iterable[str]) -> _Invocation:
        inv = _Invocation(ids)
        for msg_id in inv.ids:
            self._in_flight[msg_id] = inv
            self._finished.discard(msg_id)
            if msg_id in self._lost_queued:
                self._lost_queued.discard(msg_id)
                inv.lost = True
                inv.lost_ids.append(msg_id)
        return inv

    def end(self, inv: _Invocation) -> None:
        for msg_id in inv.ids:
            if self._in_flight.get(msg_id) is inv:
                del self._in_flight[msg_id]
            self._trimmed.discard(msg_id)
        if self._in_flight:
            self._finished.update(inv.ids)
        else:
            # Nothing older than the next run can be renewed (see renew_once),
            # so the finished set is not needed any more.
            self._finished.clear()

    async def renew_once(self, client: Any, script: Any) -> None:
        """Renew every entry this keeper holds; react to lost ones."""
        if not self._in_flight:
            return
        cfg = self.config
        # Everything older than the oldest run in flight is either done or
        # belongs to an earlier incarnation of this consumer name (same host and
        # pid after a container restart): FastStream reads with ">", so entries
        # delivered to this process are newer than anything left from before.
        # Not renewing those lets the reclaimer recover them.
        low = min(self._in_flight, key=_id_key)
        in_flight_now = {
            msg_id
            for msg_id, inv in self._in_flight.items()
            if not inv.lost and msg_id not in self._trimmed
        }
        queued: set[str] = set()
        if cfg.scan_prefetched:
            cursor = low
            while True:
                page = await asyncio.wait_for(
                    client.xpending_range(
                        cfg.stream,
                        cfg.group,
                        min=cursor,
                        max="+",
                        count=_SCAN_PAGE,
                        consumername=cfg.consumer,
                    ),
                    cfg.timeout_s,
                )
                for entry in page:
                    msg_id = _text(entry["message_id"])
                    if (
                        msg_id not in self._in_flight
                        and msg_id not in self._finished
                        and msg_id not in self._lost_queued
                    ):
                        queued.add(msg_id)
                if len(page) < _SCAN_PAGE:
                    break
                cursor = "(" + _text(page[-1]["message_id"])
        candidates = sorted(in_flight_now | queued, key=_id_key)
        for start in range(0, len(candidates), _CHUNK):
            chunk = candidates[start : start + _CHUNK]
            statuses = await asyncio.wait_for(
                script(keys=[cfg.stream], args=[cfg.group, cfg.consumer, *chunk]),
                cfg.timeout_s,
            )
            for msg_id, status in zip(chunk, statuses, strict=True):
                self._apply(msg_id, int(status), msg_id in queued)
        self._prune()

    def _prune(self) -> None:
        """Forget finished / lost-queued ids older than the oldest run in flight
        now (the scan never reaches them). Uses the state after renew_once's
        awaits: runs may have ended, all of them even, while those were pending."""
        if not self._finished and not self._lost_queued:
            return
        if not self._in_flight:
            self._finished.clear()
            self._lost_queued.clear()
            return
        low = _id_key(min(self._in_flight, key=_id_key))
        self._finished = {i for i in self._finished if _id_key(i) >= low}
        self._lost_queued = {i for i in self._lost_queued if _id_key(i) >= low}

    def _apply(self, msg_id: str, status: int, was_queued: bool) -> None:
        if status == _RENEWED:
            return
        cfg = self.config
        inv = self._in_flight.get(msg_id)
        if status == _TRIMMED:
            if inv is not None:
                # Nothing can redeliver an entry that is gone from the stream,
                # so the run is not duplicated: let it finish (its XACK clears
                # the PEL entry). Stop renewing: once the reclaimer's XCLAIM
                # drops the dangling PEL entry it would look lost.
                self._trimmed.add(msg_id)
                logger.warning(
                    "Lease renewal: entry %s was deleted from stream %s "
                    "(group %s) while being processed (MAXLEN/XTRIM/XDEL); "
                    "letting the handler finish, the entry cannot be redelivered.",
                    msg_id,
                    cfg.stream,
                    cfg.group,
                )
            return
        # Lost: the entry is not in this consumer's PEL any more.
        if inv is not None:
            if msg_id not in inv.lost_ids:
                inv.lost_ids.append(msg_id)
            if inv.lost:
                return
            inv.lost = True
            if cfg.cancel_on_lost:
                logger.error(
                    "Lease lost for entry %s on stream %s (group %s, consumer %s): "
                    "it was reclaimed for redelivery; cancelling the handler.",
                    msg_id,
                    cfg.stream,
                    cfg.group,
                    cfg.consumer,
                )
                inv.cancel("lease_lost")
            else:
                logger.error(
                    "Lease lost for entry %s on stream %s (group %s, consumer %s): "
                    "it was reclaimed for redelivery; the handler keeps running "
                    "(cancel_on_lease_lost=False) and may overlap the redelivery.",
                    msg_id,
                    cfg.stream,
                    cfg.group,
                    cfg.consumer,
                )
        elif was_queued:
            # Prefetched, handler not started yet: fail it when it starts.
            self._lost_queued.add(msg_id)
            logger.error(
                "Lease lost for queued entry %s on stream %s (group %s) before "
                "its handler started.",
                msg_id,
                cfg.stream,
                cfg.group,
            )
        # Otherwise the run finished while the renewal was in flight: its ack is
        # why the entry left the PEL.

    async def run(self, manager: "LeaseManager") -> None:
        cfg = self.config
        loop = asyncio.get_running_loop()
        delay = cfg.interval_s
        overrunning = False
        # The flag, not just cancellation, ends the loop: on CPython < 3.12
        # asyncio.wait_for inside redis-py can swallow a CancelledError.
        while manager.running:
            await asyncio.sleep(delay)
            started = loop.time()
            client, script = manager.client, manager.script
            if client is not None and script is not None:
                try:
                    await self.renew_once(client, script)
                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    logger.warning(
                        "Lease renewal failed — stream=%s group=%s consumer=%s "
                        "ids=%s: %s: %s (retrying in %.3fs)",
                        cfg.stream,
                        cfg.group,
                        cfg.consumer,
                        sorted(self._in_flight, key=_id_key),
                        type(e).__name__,
                        e,
                        cfg.interval_s,
                    )
            # Fixed rate: a slow round (several chunks, a timed-out call)
            # shortens the next wait instead of pushing every later renewal
            # back. A round slower than the interval still gets a short pause,
            # so a keeper that can't keep up doesn't run back-to-back rounds.
            elapsed = loop.time() - started
            if elapsed >= cfg.interval_s and not overrunning:
                logger.warning(
                    "Lease renewal round took %.3fs, longer than the %.3fs "
                    "interval — stream=%s group=%s consumer=%s (%d in flight); "
                    "entries may become reclaimable if this persists.",
                    elapsed,
                    cfg.interval_s,
                    cfg.stream,
                    cfg.group,
                    cfg.consumer,
                    len(self._in_flight),
                )
            overrunning = elapsed >= cfg.interval_s
            delay = max(_MIN_PAUSE_RATIO * cfg.interval_s, cfg.interval_s - elapsed)


LeaseKey = tuple[str, str, str]


class LeaseManager:
    """Owns the Redis client and one renewal task per lease keeper."""

    def __init__(self, redis_url: str, connection_kwargs: dict[str, Any] | None = None):
        self._redis_url = redis_url
        self._connection_kwargs: dict[str, Any] = connection_kwargs or {}
        self._keepers: dict[LeaseKey, LeaseKeeper] = {}
        self._tasks: dict[LeaseKey, asyncio.Task] = {}
        self.client: aioredis.Redis | None = None
        self.script: Any = None
        self.running = False

    def add(self, config: LeaseConfig) -> tuple[LeaseKey, LeaseKeeper, bool]:
        """Register (or reuse) the keeper for ``config``'s (stream, group,
        consumer). Returns ``(key, keeper, created)``; only a created keeper is
        the caller's to roll back with :meth:`discard`.

        Subscriptions sharing a key share one PEL, so they share one keeper. A
        second registration with different settings is refused rather than
        replacing a keeper that handlers already wrapped may still be using.
        """
        key = (config.stream, config.group, config.consumer)
        keeper = self._keepers.get(key)
        if keeper is not None:
            if keeper.config != config:
                raise ValueError(
                    f"lease_renewal is already configured for stream "
                    f"{config.stream!r} group {config.group!r} consumer "
                    f"{config.consumer!r} with different settings "
                    f"({keeper.config} vs {config}); subscriptions sharing a "
                    "consumer must use the same lease options."
                )
            return key, keeper, False
        keeper = LeaseKeeper(config)
        self._keepers[key] = keeper
        return key, keeper, True

    def discard(self, key: LeaseKey) -> None:
        """Remove a keeper (rolling back a partial subscribe) and its task."""
        self._keepers.pop(key, None)
        task = self._tasks.pop(key, None)
        if task is not None:
            task.cancel()

    async def start(self) -> None:
        """Open the client and start missing renewal tasks. Idempotent: also
        called for keepers registered after the first start."""
        if self.client is None:
            # decode_responses: ids come back as str. The forwarded connection
            # kwargs are resilience settings only, never decode_responses.
            self.client = aioredis.from_url(
                self._redis_url,
                **{**self._connection_kwargs, "decode_responses": True},
            )
            self.script = self.client.register_script(_RENEW_SCRIPT)
        self.running = True
        for key, keeper in self._keepers.items():
            task = self._tasks.get(key)
            if task is not None and not task.done():
                continue
            self._tasks[key] = asyncio.create_task(
                keeper.run(self),
                name=f"lease-renewal:{keeper.config.stream}:{keeper.config.group}",
            )

    async def stop(self) -> None:
        """Stop all renewal tasks and close the client."""
        self.running = False
        tasks = list(self._tasks.values())
        self._tasks.clear()
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        client, self.client, self.script = self.client, None, None
        if client is not None:
            try:
                await client.aclose()
            except Exception:
                logger.warning(
                    "Lease renewal: closing the Redis client failed", exc_info=True
                )


async def _drain(task: asyncio.Task) -> None:
    """Wait for a cancelled task to finish, ignoring its outcome."""
    try:
        await task
    except (asyncio.CancelledError, Exception):
        pass


def wrap_handler_with_lease(
    handler: Callable,
    *,
    stream: str,
    group: str,
    keeper: LeaseKeeper | None,
    message_ids: Callable[[], list[str] | None],
    max_processing_ms: int | None,
) -> Callable:
    """Run ``handler`` under a lease (``keeper``) and/or a deadline.

    The handler runs in a child task so the lease keeper (lost lease) or the
    deadline can cancel it without cancelling FastStream's consume loop. A
    cancellation of the wrapper itself (agent stop) is forwarded to the handler.
    ``message_ids`` returns the stream ids of the message being handled (from
    FastStream's context); without them the handler runs unleased (logged).

    Sync handlers run in a worker thread, which cannot be interrupted: a lost
    lease or a missed deadline takes effect when the thread returns (its result
    is discarded and the error raised).
    """
    is_async = is_async_callable(handler)
    deadline_s = max_processing_ms / 1000 if max_processing_ms is not None else None

    def _error(inv: _Invocation) -> Exception:
        if inv.reason == "timeout" and max_processing_ms is not None:
            return ProcessingTimeoutError(stream, group, inv.ids, max_processing_ms)
        return LeaseLostError(stream, group, inv.ids, inv.lost_ids or None)

    def _read_ids() -> list[str]:
        try:
            ids = message_ids()
        except Exception:
            if keeper is not None:
                logger.error(
                    "Lease renewal: could not read the message ids on %s (group "
                    "%s); handling the message without a lease",
                    stream,
                    group,
                    exc_info=True,
                )
            return []
        if not ids and keeper is not None:
            logger.warning(
                "Lease renewal: no stream ids for the message on %s (group %s); "
                "handling it without a lease",
                stream,
                group,
            )
        return list(ids or ())

    @functools.wraps(handler)
    async def leased_handler(*args, **kwargs):
        ids = _read_ids()
        lease = keeper if ids else None
        inv = lease.begin(ids) if lease is not None else _Invocation(ids)
        try:
            if inv.lost and lease is not None and lease.config.cancel_on_lost:
                raise LeaseLostError(stream, group, inv.ids, inv.lost_ids or None)
            task = asyncio.create_task(call_handler(handler, is_async, *args, **kwargs))
            inv.task = task
            # Nothing awaits between begin() and here, so the keeper can't have
            # cancelled the run yet; honour it anyway should that ever change.
            if inv.reason is not None:
                task.cancel()
            try:
                done, _ = await asyncio.wait({task}, timeout=deadline_s)
                if not done:
                    logger.error(
                        "Handler on %s (group %s) exceeded max_processing_ms=%s "
                        "for %s; cancelling it, the entry is left for retry.",
                        stream,
                        group,
                        max_processing_ms,
                        ", ".join(inv.ids) or "?",
                    )
                    inv.cancel("timeout")
                    await asyncio.wait({task})
            except asyncio.CancelledError:
                # asyncio.wait never raises the child's cancellation, so this is
                # the wrapper's own (agent stop): forward it to the handler. No
                # Task.cancelling() needed, which Python 3.10 doesn't have.
                task.cancel()
                await _drain(task)
                raise
            # The task is done: result() doesn't suspend, so from here on no
            # outer cancellation can be mistaken for the handler's outcome.
            try:
                result = task.result()
            except asyncio.CancelledError:
                if inv.reason is None:
                    raise  # the handler cancelled itself
                raise _error(inv) from None
            except Exception as exc:
                if inv.reason is not None:
                    raise _error(inv) from exc
                raise
            if inv.reason is not None:
                # The handler swallowed the cancellation (or a sync handler's
                # thread returned late); the entry is still not ours (lost) or
                # overdue (timeout), so don't let it be acked.
                raise _error(inv)
            return result
        finally:
            if lease is not None:
                lease.end(inv)

    return leased_handler
