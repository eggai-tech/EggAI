"""
Token rotation with a streaming credential provider (Azure Managed Redis /
Microsoft Entra ID): every connection the transport holds is re-authenticated
with each new token, so none is dropped when the old token expires.

Integration tests against a real Redis at localhost:6379. Entra ID is emulated
with ACL users: each token is a fresh ACL user (the token's ``oid`` claim is
the username, as with Entra), and a token "expires" by ``ACL DELUSER``, which
makes Redis close every connection still authenticated as that user, as Azure
does with a connection whose token expired and was not replaced via ``AUTH``.
The credential provider is ``redis-entraid``'s own when it is installed, else
an equivalent built on the same redis-py ``TokenManager``.
"""

import asyncio
import itertools
import logging
import time
import uuid
from dataclasses import dataclass

import pytest
import pytest_asyncio
import redis
import redis.asyncio as aioredis
from redis.auth.token import SimpleToken
from redis.auth.token_manager import RetryPolicy, TokenManager, TokenManagerConfig
from redis.credentials import CredentialProvider, StreamingCredentialProvider

from eggai import Agent, Channel
from eggai.transport import RedisTransport, redis_reauth
from eggai.transport.redis_reauth import _ReAuthFanOut, register_pool, unregister_pool

TOKEN_TTL_S = 2.0
REFRESH_RATIO = 0.5  # a new token at half the TTL leaves 1 s to re-AUTH


class _AclIdentityProvider:
    """Mints each token as a fresh ACL user. Like MSAL, returns the cached token
    unless asked to refresh or it has expired, so new connections authenticate
    as the current user."""

    def __init__(self, admin: redis.Redis, prefix: str) -> None:
        self._admin = admin
        self._prefix = prefix
        self._seq = itertools.count()
        self._token: SimpleToken | None = None
        self.issued: list[SimpleToken] = []

    def request_token(self, force_refresh: bool = False) -> SimpleToken:
        if self._token is None or force_refresh or self._token.is_expired():
            user = f"{self._prefix}-{next(self._seq)}"
            password = uuid.uuid4().hex
            self._admin.execute_command(
                "ACL", "SETUSER", user, "on", f">{password}", "~*", "&*", "+@all"
            )
            now_ms = time.time() * 1000
            self._token = SimpleToken(
                password, now_ms + TOKEN_TTL_S * 1000, now_ms, {"oid": user}
            )
            self.issued.append(self._token)
        return self._token


class _EntraLikeProvider(StreamingCredentialProvider):
    """``redis_entraid.cred_provider.EntraIdCredentialsProvider``, for when it is
    not installed: a TokenManager plus a listener with one ``on_next`` slot."""

    def __init__(self, identity_provider, token_manager_config) -> None:
        from redis.auth.token_manager import CredentialsListener

        self._token_mgr = TokenManager(identity_provider, token_manager_config)
        self._listener = CredentialsListener()
        self._is_streaming = False

    def get_credentials(self):
        raise NotImplementedError  # async clients only

    async def get_credentials_async(self):
        token = (await self._token_mgr.acquire_token_async()).get_token()
        if not self._is_streaming:
            await self._token_mgr.start_async(self._listener, skip_initial=True)
            self._is_streaming = True
        return token.try_get("oid"), token.get_value()

    def on_next(self, callback):
        self._listener.on_next = callback

    def on_error(self, callback):
        self._listener.on_error = callback

    def is_streaming(self) -> bool:
        return self._is_streaming


def _make_provider(idp):
    config = TokenManagerConfig(
        expiration_refresh_ratio=REFRESH_RATIO,
        lower_refresh_bound_millis=0,
        token_request_execution_timeout_in_ms=1000,
        retry_policy=RetryPolicy(max_attempts=3, delay_in_ms=10),
    )
    try:
        from redis_entraid.cred_provider import EntraIdCredentialsProvider
    except ImportError:
        return _EntraLikeProvider(idp, config)
    return EntraIdCredentialsProvider(idp, config)


async def _expire_tokens(admin: aioredis.Redis, idp: _AclIdentityProvider) -> None:
    """Delete each token's user once the token expires, as the server would."""
    expired: set[str] = set()
    while True:
        now_ms = time.time() * 1000
        for token in list(idp.issued):
            user = token.try_get("oid")
            if user not in expired and token.get_expires_at_ms() <= now_ms:
                await admin.execute_command("ACL", "DELUSER", user)
                expired.add(user)
        await asyncio.sleep(0.05)


@pytest_asyncio.fixture
async def admin():
    client = aioredis.Redis(host="localhost", port=6379, decode_responses=True)
    yield client
    await client.aclose()


@pytest_asyncio.fixture
async def sync_admin():
    client = redis.Redis(host="localhost", port=6379, decode_responses=True)
    yield client
    for user in client.execute_command("ACL", "USERS"):
        if user.startswith("reauth-"):
            client.execute_command("ACL", "DELUSER", user)
    client.close()


@pytest.mark.asyncio
async def test_connections_survive_token_expiry(admin, sync_admin, caplog):
    """Messages keep flowing across several token lifetimes, and every client
    (broker, reclaimer, group monitor, delete-on-ack) keeps working: before the
    fix only new connections got a new token, so each expiry dropped the open
    ones and the next command on them failed (e.g. the delete-on-ack XACK+XDEL,
    leaving the handled entry in the PEL to be re-delivered)."""
    test_id = uuid.uuid4().hex[:8]
    idp = _AclIdentityProvider(sync_admin, f"reauth-{test_id}")
    provider = _make_provider(idp)
    transport = RedisTransport(
        url="redis://localhost:6379",
        credential_provider=provider,
        group_monitor_interval_s=0.2,
    )
    agent = Agent(f"reauth-{test_id}", transport=transport)
    channel = Channel(f"reauth-ch-{test_id}", transport=transport)
    stream = f"eggai.reauth-ch-{test_id}"

    seen: list[int] = []

    @agent.subscribe(
        channel=channel,
        delete_on_ack=True,
        retry_on_idle_ms=10_000,
        retry_reclaim_interval_s=0.2,
    )
    async def handler(message):
        seen.append(message["n"])

    caplog.set_level(logging.WARNING, logger="eggai")
    expirer = asyncio.create_task(_expire_tokens(admin, idp))
    await agent.start()
    try:
        # Three token lifetimes, a message every 100 ms.
        deadline = time.monotonic() + 3 * TOKEN_TTL_S
        n = 0
        while time.monotonic() < deadline:
            await channel.publish({"type": "t", "n": n})
            n += 1
            await asyncio.sleep(0.1)
        for _ in range(50):
            if len(seen) >= n and await admin.xlen(stream) == 0:
                break
            await asyncio.sleep(0.1)

        assert len(idp.issued) >= 4  # the tokens did rotate
        assert sorted(seen) == list(range(n))  # each handled exactly once
        assert await admin.xlen(stream) == 0  # every delete_on_ack succeeded
        problems = [
            r.getMessage() for r in caplog.records if r.levelno >= logging.WARNING
        ]
        assert problems == []
    finally:
        await agent.stop()
        expirer.cancel()
        provider._token_mgr.stop()
    # disconnect() unregistered the broker's and the background clients' pools
    assert len(redis_reauth._fan_outs[id(provider)][1]) == 0


@pytest.mark.asyncio
async def test_transports_sharing_a_provider_are_all_reauthenticated(admin, sync_admin):
    """A provider holds one ``on_next`` callback. With two transports (one per
    agent) sharing it, the one registered last must not take over: no
    connection of either transport stays on the replaced token, and both
    transports' consumers carry on with the new one."""
    test_id = uuid.uuid4().hex[:8]
    idp = _AclIdentityProvider(sync_admin, f"reauth-{test_id}")
    provider = _make_provider(idp)
    agents = []
    for i in range(2):
        transport = RedisTransport(
            url="redis://localhost:6379", credential_provider=provider
        )
        agent = Agent(f"reauth-{test_id}-{i}", transport=transport)
        channel = Channel(f"reauth-ch-{test_id}-{i}", transport=transport)

        @agent.subscribe(channel=channel, retry_on_idle_ms=10_000)
        async def handler(message):
            pass

        agents.append(agent)
    for agent in agents:
        await agent.start()
    try:
        # The token manager refreshes once right at start; wait for the next
        # refresh (at half the TTL), which comes after every connection is open.
        await asyncio.sleep(0.3)
        before = idp.issued[-1]
        for _ in range(30):
            if idp.issued[-1] is not before:
                break
            await asyncio.sleep(0.1)
        current = idp.issued[-1].try_get("oid")
        assert current != before.try_get("oid")
        for _ in range(10):  # in-use connections reconnect on release
            users = [
                c["user"]
                for c in await admin.client_list()
                if c["user"].startswith(f"reauth-{test_id}")
            ]
            if before.try_get("oid") not in users:
                break
            await asyncio.sleep(0.1)
        assert before.try_get("oid") not in users
        # each transport's consumer read loop is back, on the new token
        assert users.count(current) >= 2
    finally:
        for agent in agents:
            await agent.stop()
        provider._token_mgr.stop()


class _Pool:
    """A pool without redis-py's internals: the fan-out falls back to
    ``re_auth_callback``."""

    def __init__(self, fail: bool = False) -> None:
        self.tokens: list[str] = []
        self.fail = fail

    async def re_auth_callback(self, token):
        if self.fail:
            raise redis.ConnectionError("Connection closed by server.")
        self.tokens.append(token)


@pytest.mark.asyncio
async def test_one_failing_pool_does_not_stop_the_others(caplog):
    fan_out = _ReAuthFanOut()
    pools = [_Pool(), _Pool(fail=True), _Pool()]
    for pool in pools:
        fan_out.add(pool)
    await fan_out.on_next("token-2")
    assert pools[0].tokens == ["token-2"]
    assert pools[2].tokens == ["token-2"]
    assert "re-authentication failed" in caplog.text

    # A refresh error is logged, not raised into the provider's refresh task.
    await fan_out.on_error(RuntimeError("IdP unreachable"))
    assert "failed to refresh its token: IdP unreachable" in caplog.text


def test_pools_without_a_streaming_provider_are_not_registered():
    """Password, ACL user or no auth: nothing to re-authenticate."""
    before = len(redis_reauth._fan_outs)
    register_pool(aioredis.ConnectionPool(host="localhost"))
    register_pool(aioredis.ConnectionPool(host="localhost", password="pw"))
    assert len(redis_reauth._fan_outs) == before


@dataclass
class _StaticProvider(CredentialProvider):
    """A plain dataclass: unhashable (``eq=True`` sets ``__hash__ = None``)."""

    username: str = "default"
    password: str = "unused"  # the default user is nopass: any password works

    def get_credentials(self):
        return self.username, self.password


@dataclass
class _DataclassStreamingProvider(StreamingCredentialProvider):
    callbacks: list

    def get_credentials(self):
        return ("default", "unused")

    def on_next(self, callback):
        self.callbacks.append(callback)

    def on_error(self, callback):
        pass

    def is_streaming(self) -> bool:
        return True


@pytest.mark.asyncio
async def test_static_unhashable_provider_starts_and_stops():
    """A static provider is never registered, and closing its clients (first in
    connect(), after creating the groups) must not look it up either."""
    test_id = uuid.uuid4().hex[:8]
    transport = RedisTransport(
        url="redis://localhost:6379", credential_provider=_StaticProvider()
    )
    agent = Agent(f"reauth-static-{test_id}", transport=transport)
    channel = Channel(f"reauth-static-ch-{test_id}", transport=transport)
    seen = []

    @agent.subscribe(channel=channel, delete_on_ack=True, retry_on_idle_ms=10_000)
    async def handler(message):
        seen.append(message["n"])

    await agent.start()
    try:
        await channel.publish({"type": "t", "n": 1})
        for _ in range(50):
            if seen:
                break
            await asyncio.sleep(0.1)
        assert seen == [1]
    finally:
        await agent.stop()


def test_unhashable_streaming_provider_is_registered_and_unregistered():
    provider = _DataclassStreamingProvider(callbacks=[])
    pool = aioredis.ConnectionPool(host="localhost", credential_provider=provider)
    register_pool(pool)
    register_pool(pool)  # idempotent: one callback on the provider
    assert len(provider.callbacks) == 1
    assert len(redis_reauth._fan_outs[id(provider)][1]) == 1
    unregister_pool(pool)
    assert len(redis_reauth._fan_outs[id(provider)][1]) == 0
