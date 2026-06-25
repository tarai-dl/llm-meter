# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- `py.typed` marker for downstream type checker support
- `SECURITY.md` with vulnerability reporting policy

### Changed
- YAML error messages now include line numbers for easier debugging

### Fixed
- Graceful shutdown for `serve` and `export-prometheus` via SIGTERM/SIGINT
- Bearer token comparison uses constant-time `hmac.compare_digest`
- Webhook delivery catches all network exceptions, preventing cron alert crashes
- Prometheus label escaping now handles `\r` characters
- `render_dashboard` receives `top` parameter from `export_bundle`
- SQLite connections enable WAL journal mode and 5s busy timeout
- Parser strips `\r\n` line endings (Windows log compatibility)
- Parser detects microsecond timestamps (10^15–10^18 range)
- Exit codes standardized: `0` success, `1` no data, `1` server startup failure

## [0.23.0] - 2026-06-09

### Added
- High auth prefix diversity abuse signal detection
- Dashboard supports recent-window filtering via `?limit=N`
- Auth token support for dashboard and Prometheus servers (`--auth-token`)
- YAML list support: inline `[a, b]` and indented `- item`
- Export bundle includes HTML report with consistent top-N values

### Fixed
- `NameError` in `Report.signals()` when 10+ unique auth prefixes present
- Nanosecond timestamp detection threshold corrected to `> 10^18`
- `max_requests_per_ip` alert rule checks all IPs, not just top 10
- `_optional_int` and `_optional_float` handle non-numeric config values gracefully
