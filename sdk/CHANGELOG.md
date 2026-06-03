# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed
- Bump `fastmcp` from `^2.14.0` to `^3.0.0` (resolves to 3.4.0), which pulls in `authlib` 1.7.2. The MCP adapter now uses `Tool.to_mcp_tool()` to read tool schemas, since fastmcp 3.x `list_tools()` returns `FunctionTool` objects that expose schemas via `parameters`/`output_schema` instead of `inputSchema`/`outputSchema`.

## [Unreleased]

### Added
- **Distributed tracing via OpenTelemetry**: Agents now propagate a shared `trace_id` across every message hop. Opt-in via `setup_tracing()`; zero-cost when not configured.

### Fixed
- **RedisTransport** (#225): Retry and DLQ stream keys are now per-handler
  (`{channel}.{handler_suffix}.retry` / `.dlq`) instead of per-channel.
  Previously, multiple handlers subscribing to the same channel with different
  consumer groups shared a single `{channel}.retry` stream, so one handler's
  reclaimed failure would be redelivered to **every** handler on that channel
  via its auto-created `-retry` group. This caused work amplification (N
  replays per nack, where N is the number of consumer groups on the channel)
  and visible duplicate side-effects in downstream systems with non-idempotent
  handlers.
- **RedisTransport**: A permanently-unparseable ("poison") retry message is now
  routed to the DLQ — or dropped with an error log when no DLQ is configured —
  instead of being re-queued to the retry stream forever. Its retry count can
  never be incremented, so it would previously livelock the per-handler retry
  stream.
- **RedisTransport**: The auto-created retry-stream subscriber now always reads
  only new entries (`last_id=">"`) regardless of the main subscription's
  `last_id`. Restarting with `last_id="0"` to replay the main backlog no longer
  also replays the retry stream's history on every restart.
- **RedisTransport**: A `RedisTransport` shared across multiple `Agent`s no
  longer spawns duplicate consumer loops or orphans its consumer-group monitor
  task when each agent calls `connect()`. Re-entrant `connect()` now starts only
  not-yet-running subscribers and reuses the existing monitor.
- **Tracing**: Retry-stream consumption now emits spans with the retry stream as
  `messaging.destination` instead of the original channel, so retry attempts can
  be observed separately from main-stream processing.
- **RedisTransport**: `subscribe()` now rolls back the in-memory reclaimer configs
  and stream-subscription entries it registered if retry-stream setup fails, so a
  retried `start()` no longer accumulates orphaned registrations. Identical
  stream-group subscriptions are also de-duplicated.

### Changed
- **RedisTransport**: `retry_on_idle_ms` now rejects `ack_policy=AckPolicy.ACK`
  and `AckPolicy.ACK_FIRST` with a `ValueError`. Those acknowledge messages even
  when the handler fails, emptying the PEL the reclaimer scans, which would
  silently disable retries and the DLQ. Use the default `NACK_ON_ERROR`.

### Migration
- **Breaking on-wire change.** Existing inflight messages in `{channel}.retry`
  and `{channel}.dlq` streams will not be picked up by upgraded consumers —
  they will continue to exist but new retries will land in the per-handler
  streams. Drain the legacy streams before deploying, or `XADD` any pending
  entries into the new per-handler keys.

## [0.2.14] - 2026-03-20

### Fixed
- **RedisTransport**: Auto-recover from NOGROUP errors when Redis loses streams
  (restart without persistence, failover, memory eviction). A background stream
  group monitor periodically ensures consumer groups exist via `XGROUP CREATE`
  with `MKSTREAM`, and `PendingReclaimerManager` now recreates consumer groups
  on NOGROUP errors instead of logging unhandled exceptions.

### Changed
- Bump `faststream` from 0.6.5 to 0.6.6 — fixes `xautoclaim` crash on Redis < 7.0.
- Bump `a2a-sdk` from 0.3.22 to 0.3.24.
- Bump `pyasn1` from 0.6.1 to 0.6.2 — fixes CVE-2026-23490.

## [0.2.13] - 2026-03-14

### Changed
- **CI**: Replace `skip-changelog` label with path-based auto-skip; changelog is only
  required when SDK code changes. Strengthen validation to require at least one bullet entry.
- **CI**: Replace broken `auto-tag.yaml` with manual `tag-release.yaml` workflow.
  Fix `release.yaml` PR creation bug (missing `--head` flag).

## [0.2.12] - 2026-03-12

### Added
- **RedisTransport**: SDK-managed PEL reclaimer via new `retry_on_idle_ms` opt-in
  kwarg on `agent.subscribe()`. With `NACK_ON_ERROR` (the default), a handler
  exception leaves the message in the Redis Pending Entries List forever because
  FastStream only reads new messages. Setting `retry_on_idle_ms` enables a
  background reclaimer that:
  - Pages through `XPENDING` and claims entries idle longer than the threshold.
  - Moves them to a dedicated `{channel}.retry` stream (no duplicate delivery).
  - Subscribes the same handler to the retry stream automatically.
  - Runs a second reclaimer on the retry stream that re-queues back to itself
    (prevents unbounded `.retry.retry.retry` chains).
  - Injects `_retry_count` and `_original_message_id` into the message body for
    handler-level idempotency and deduplication.
  - Is restart-safe: the Redis client is recreated on each `start()` call.
  - `min_idle_time` (FastStream XAUTOCLAIM) and `retry_on_idle_ms` are mutually
    exclusive on the same subscription; mixing them raises `ValueError` at
    decoration time.
- **RedisTransport**: Dead Letter Queue (DLQ) with configurable `max_retries`
  (default 5). Poison messages that exceed the retry limit are routed to a
  `{channel}.dlq` stream instead of retrying forever. The DLQ is terminal — no
  automatic reclaimer watches it. Key details:
  - `max_retries=5` means 6 total handler calls (1 original + 5 retries); on the
    6th reclaim cycle the message is moved to the DLQ.
  - Set `max_retries=None` to disable the DLQ and get unlimited retries
    (previous behavior).
  - Optional `on_dlq` callback (sync or async) fires when a message lands in the
    DLQ — useful for alerting or metrics. Errors in the callback are logged but
    never prevent the DLQ write.
  - Both reclaimers (main stream and retry stream) enforce the same threshold.
  - Unparseable messages (binary parse failure) return `_retry_count=0` and are
    never mistakenly routed to the DLQ.

## [0.2.11] - 2026-01-28

### Fixed
- **RedisTransport**: Messages are no longer acknowledged when handlers raise exceptions
  - Set default `ack_policy` to `AckPolicy.NACK_ON_ERROR` for reliable message delivery
  - Failed messages now remain in the Pending Entries List (PEL) for redelivery
  - Added `min_idle_time` parameter support for automatic claiming of pending messages
  - Added test verifying error handling and message recovery behavior

## [0.2.9] - 2025-12-30

### Added
- Enhanced release process with `make release VERSION=x.y.z` command
- Changelog enforcement in CI for pull requests
- Release candidate support with `make release-rc VERSION=x.y.zrc1`
- `Channel.ensure_exists()` for pre-creating Kafka topics

### Changed
- Kafka topics now auto-create on first use
- Release workflow now uses git tags for versioning
- Version now uses single source of truth (`pyproject.toml`) via `importlib.metadata`
- Consolidated repository structure: removed duplicate docs from `sdk/`, moved to `docs/`
- Moved issue templates from `sdk/.github/` to root `.github/`

### Fixed
- Redis transport parameter handling

## [0.2.8] - 2025-11-12

### Fixed
- **RedisTransport**: Fixed consumer group message delivery issue
  - Changed default `last_id` parameter from `"$"` to `">"` for consumer groups
  - `"$"` was causing messages to be ignored if published before consumer started
  - `">"` correctly reads pending messages in the consumer group (Redis Streams standard)
- **RedisTransport.disconnect()**: Enhanced cleanup process
  - Added proper 4-step shutdown sequence: stop subscribers → cancel tasks → wait → close broker
  - Added error handling for graceful degradation during shutdown
  - Prevents resource leaks and ensures clean disconnection

### Changed
- **RedisTransport.connect()**: Simplified subscriber initialization
  - Removed redundant `subscriber.start()` calls (already handled by `broker.start()`)
  - Added task reference tracking to prevent garbage collection
  - Improved code clarity and follows FastStream's design patterns

## [0.2.7] - 2025-11-12

### Added
- **RedisTransport**: New transport implementation based on FastStream's RedisBroker
  - Uses Redis Streams with consumer groups for reliable message delivery
  - Supports message filtering via middleware (filter_by_message, data_type, filter_by_data)
  - Compatible with all existing Agent and Channel APIs
  - Comprehensive test suite included
  - Default connection: `redis://localhost:6379`
- Added `redis` extra to FastStream dependency in pyproject.toml

### Changed
- Updated FastStream dependency to include both kafka and redis extras

## [0.2.6] - 2025-01-02

Initial tracked release. See [GitHub releases](https://github.com/eggai-tech/eggai/releases) for earlier versions.
