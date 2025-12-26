# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Enhanced release process with `make release VERSION=x.y.z` command
- Changelog enforcement in CI for pull requests
- Release candidate support with `make release-rc VERSION=x.y.zrc1`

### Changed
- Release workflow now uses git tags for versioning
- Version now uses single source of truth (`pyproject.toml`) via `importlib.metadata`
- Consolidated repository structure: removed duplicate docs from `sdk/`, moved to `docs/`
- Moved issue templates from `sdk/.github/` to root `.github/`

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
