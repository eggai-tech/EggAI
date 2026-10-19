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

It also does not use redis-py's ``ConnectionPool.re_auth_callback``. For a
connection in use, that defers ``AUTH`` to ``release()``, which
puts the connection back on the available list and drops the pool lock *before*
sending ``AUTH`` and reading its reply. ``release()`` runs inside
``execute_command`` before the command's result is returned, so the caller is
still holding a reply it has already read. If another task (e.g. FastStream's
``.retry`` subscriber, which shares the broker's pool) takes the connection
meanwhile and reads from it, asyncio refuses the second reader (``RuntimeError:
readuntil() called while another coroutine is already waiting``), redis-py closes
the connection, and the pending ``AUTH`` read fails with ``ConnectionError``. That
error leaves ``release()`` and so ``execute_command``, discarding the reply already
read: for an ``XREADGROUP`` the delivered entries sit in the PEL unhandled until
the reclaimer re-delivers them. Instead, on a new token each pool's idle
connections are closed and its in-use ones marked to reconnect on release, both
under the pool lock, so no ``AUTH`` is ever in flight on a connection another task
can take: every connection's next command dials anew, authenticating with the
provider's current token like any new connection.
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

    def __contains__(self, pool: Any) -> bool:
        return pool in self._pools

    async def on_next(self, token: Any) -> None:
        # One pool failing must not leave the others on the old token.
        for pool in list(self._pools):
            try:
                await _reconnect_with_new_token(pool)
            except Exception:
                logger.warning(
                    "Redis re-authentication failed for a connection pool; its "
                    "connections reconnect with a fresh token when next used",
                    exc_info=True,
                )

    async def on_error(self, error: Exception) -> None:
        # redis-py's token manager calls this once its retry policy is used up
        # and then schedules no further refresh, and the provider never restarts
        # it (it still reports itself as streaming). Raising, as redis-py's own
        # handler does, would not change that. Connections keep the current
        # token until it expires and are then closed by the server; a reconnect
        # authenticates with whatever token the provider hands out then.
        logger.error(
            "Redis credential provider failed to refresh its token; token renewal "
            "has stopped, so connections are dropped when the current token "
            "expires and then reconnect with a fresh one: %s",
            error,
        )


async def _reconnect_with_new_token(pool: Any) -> None:
    """Make every connection of ``pool`` authenticate with the new token on its
    next command. No token is passed: a reconnecting connection asks the provider,
    which hands out the new one (see the module docstring for why not
    ``re_auth_callback``)."""
    # redis-py >= 7.2: release() disconnects a connection marked for reconnect
    # and clears the mark (7.0/7.1 never clear it, so such a connection would
    # be dropped again on every later release).
    async with pool._lock:
        for conn in pool._in_use_connections:
            conn.mark_for_reconnect()  # release() disconnects it, under the lock
        # As redis-py's own ConnectionPool.disconnect(): one connection failing
        # to close (e.g. a close timeout) must not leave the rest on the old token.
        await asyncio.gather(
            *(conn.disconnect() for conn in pool._available_connections),
            return_exceptions=True,
        )


# id(provider) -> (provider, its fan-out), while any pool is registered against
# it. Keyed by id, not by the provider: a provider need not be hashable (a plain
# @dataclass is not) or weakly referenceable. The entry holds the provider, so
# its id is not reused while the entry exists.
_fan_outs: dict[int, tuple[Any, _ReAuthFanOut]] = {}


def _streaming_provider(pool: Any) -> StreamingCredentialProvider | None:
    provider = getattr(pool, "connection_kwargs", {}).get("credential_provider")
    return provider if isinstance(provider, StreamingCredentialProvider) else None


def register_pool(pool: Any) -> None:
    """Re-authenticate ``pool``'s connections whenever its credential provider
    rotates the token. A no-op for a pool without a streaming credential provider
    (password, ACL user, a static provider or no authentication). Idempotent."""
    provider = _streaming_provider(pool)
    if provider is None:
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
        if not entry[1]:
            # Drop the provider with its last pool. Its on_next stays the
            # emptied fan-out (a no-op) until a later register_pool installs a
            # new one.
            del _fan_outs[id(provider)]


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
