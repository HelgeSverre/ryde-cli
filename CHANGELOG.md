# Changelog

## 0.1.1 — 2026-10-16

- Fetch ride archives from the requested start year, including history before 2024.
- Skip future-year partitions and retain pagination, deduplication, and date filtering.
- Report config, export, skill installation, and API response failures with readable errors.
- Mark background stats jobs failed when worker startup or configuration loading fails.
- Upgrade to MCP SDK 2.3 and preserve expected errors for tools and resources through public APIs.
- Update dashboard dependencies, Vite, TypeScript, and CodeQL; rebuild bundled assets.
- Read the CLI version from package metadata.

## 0.1.0 — 2026-10-16

Initial public release on PyPI.

- Guided SMS authentication with a local duplicate-request guard.
- Account, ride, route, pass, payment, and city-fare queries.
- JSON, CSV, TSV, and table output; owner-only file exports.
- Ride summaries and current-price RidePass comparisons.
- A stdio MCP server with 20 tools and two resources.
- uv development workflow, generated command reference, and GitHub CI.
- Bundled local map dashboard, resumable data exports, and background MCP jobs.
- Portable Claude Code/Codex skill with explicit scoped installation.
