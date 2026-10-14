"""Re-authentication of the transport's Redis connections when a streaming
credential provider rotates its token.

A ``StreamingCredentialProvider`` (``redis-entraid`` for Azure Managed Redis /
Microsoft Entra ID, or any other rotating-token provider) renews its token in the
background and hands each new one to the callback set with ``on_next``. Servers
like Azure Managed Redis close a connection whose token has expired unless the
client re-sends ``AUTH`` with the new one, so every open connection must be
re-authenticated on rotation, not only connections opened later.

redis-py wires that up only for a client built as ``Redis(credential_provider=...)``.
The transport's clients are built differently: FastStream's broker client and the
transport's background clients (reclaimer, group monitor, delete-on-ack) all use
``Redis.from_pool(ConnectionPool(credential_provider=...))``, which registers the
re-auth hook with ``credential_provider=None``. With no callback set, redis-py's
token manager then stops renewing altogether ("No registered callback for token
renewal task. Renewal cancelled"), so every connection is dropped when the token
it opened with expires. Even through the redis-py hook, ``on_next`` is a single slot
(``redis-entraid`` keeps the last callback set), so with several pools sharing one
provider only the pool registered last would be re-authenticated.

This module keeps one callback per provider that fans each new token out to every
pool registered against it.

It also does not use redis-py's ``ConnectionPool.re_auth_callback`` where it can
avoid it. That sends ``AUTH`` on a connection in use only once the connection is
released, *after* putting it back on the available list and dropping the pool
lock, so another task can take the connection and send its own command before the
``AUTH`` reply is read. The replies then cross: e.g. an ``XREADGROUP`` reply is
read as the ``AUTH`` reply and discarded, and the entries it delivered sit in the
PEL unhandled. Instead, on a new token each pool's idle connections are closed
and its in-use ones marked to reconnect on release, both under the pool lock, so
every connection's next command dials anew, authenticating with the provider's
current token like any new connection.
"""

from __future__ import annotations

import asyncio
import logging
import weakref
from typing import Any

import redis.asyncio as aioredis
from redis.credentials import StreamingCredentialProvider

logger = logging.getLogger(__name__)


class _ReAuthFanOut:
    """The ``on_next`` / ``on_error`` callbacks installed on one provider."""

    def __init__(self) -> None:
        # Weak, so a pool that is closed and dropped is not kept alive (or
        # re-authenticated) by its provider.
        self._pools: weakref.WeakSet[Any] = weakref.WeakSet()

    def add(self, pool: Any) -> None:
        self._pools.add(pool)

    def discard(self, pool: Any) -> None:
        self._pools.discard(pool)

    def __len__(self) -> int:
        return len(self._pools)

    async def on_next(self, token: Any) -> None:
        # One pool failing must not leave the others on the old token.
        for pool in list(self._pools):
            try:
                await _reconnect_with_new_token(pool, token)
            except Exception:
                logger.warning(
                    "Redis re-authentication failed for a connection pool; its "
                    "connections reconnect with a fresh token when next used",
                    exc_info=True,
                )

    async def on_error(self, error: Exception) -> None:
        # redis-py's own handler raises here, inside the provider's refresh
        # task. Log instead: connections keep the current token until it
        # expires, and a later refresh may still succeed.
        logger.error("Redis credential provider failed to refresh its token: %s", error)


async def _reconnect_with_new_token(pool: Any, token: Any) -> None:
    """Make every connection of ``pool`` authenticate with the new token on its
    next command (see the module docstring for why not ``re_auth_callback``)."""
    lock = getattr(pool, "_lock", None)
    idle = getattr(pool, "_available_connections", None)
    in_use = getattr(pool, "_in_use_connections", None)
    if lock is None or idle is None or in_use is None:
        # Not a redis-py pool as we know it: leave it to its own re-auth.
        await pool.re_auth_callback(token)
        return
    async with lock:
        for conn in in_use:
            conn.mark_for_reconnect()  # release() disconnects it, under the lock
        # As redis-py's own ConnectionPool.disconnect(): one connection failing
        # to close (e.g. a close timeout) must not leave the rest on the old token.
        await asyncio.gather(
            *(conn.disconnect() for conn in idle), return_exceptions=True
        )


# id(provider) -> (provider, its fan-out). Keyed by id, not by the provider:
# a provider need not be hashable (a plain @dataclass is not) or weakly
# referenceable. The entry holds the provider, so its id is not reused while
# the entry exists; providers normally live as long as the process.
_fan_outs: dict[int, tuple[Any, _ReAuthFanOut]] = {}


def _streaming_provider(pool: Any) -> StreamingCredentialProvider | None:
    provider = getattr(pool, "connection_kwargs", {}).get("credential_provider")
    return provider if isinstance(provider, StreamingCredentialProvider) else None


def register_pool(pool: Any) -> None:
    """Re-authenticate ``pool``'s connections whenever its credential provider
    rotates the token. A no-op for a pool without a streaming credential provider
    (password, ACL user, a static provider or no authentication). Idempotent."""
    provider = _streaming_provider(pool)
    if provider is None or not hasattr(pool, "re_auth_callback"):
        return
    entry = _fan_outs.get(id(provider))
    if entry is None:
        fan_out = _ReAuthFanOut()
        _fan_outs[id(provider)] = (provider, fan_out)
        # The provider holds one callback; ours covers every pool. A client
        # built elsewhere as Redis(credential_provider=<same provider>) would
        # replace it, so give such clients their own provider instance.
        # Typed as sync callbacks; the token manager of an async client awaits
        # them, as it does redis-py's own async re-auth listener.
        provider.on_next(fan_out.on_next)  # type: ignore[arg-type]
        provider.on_error(fan_out.on_error)  # type: ignore[arg-type]
    else:
        fan_out = entry[1]
    fan_out.add(pool)


def unregister_pool(pool: Any) -> None:
    """Stop re-authenticating ``pool`` (it is being closed)."""
    provider = _streaming_provider(pool)
    entry = _fan_outs.get(id(provider)) if provider is not None else None
    if entry is not None:
        entry[1].discard(pool)


def open_client(
    connection_kwargs: dict[str, Any], *, decode_responses: bool
) -> aioredis.Redis:
    """A client on its own pool, dialled with ``connection_kwargs`` and
    re-authenticated on token rotation. A ConnectionPool (rather than
    ``Redis(**kwargs)``) because the broker's dict can carry
    ``connection_class``/``path`` for ``rediss://`` and ``unix://``, which the
    ``Redis`` constructor rejects. ``decode_responses`` is pinned per client."""
    pool = aioredis.ConnectionPool(
        **{**connection_kwargs, "decode_responses": decode_responses}
    )
    register_pool(pool)
    return aioredis.Redis.from_pool(pool)


async def close_client(client: aioredis.Redis) -> None:
    """Close a client from :func:`open_client` and stop re-authenticating it."""
    pool = getattr(client, "connection_pool", None)
    if pool is not None:
        unregister_pool(pool)
    await client.aclose()
