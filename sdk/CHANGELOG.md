# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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

Previous release...
