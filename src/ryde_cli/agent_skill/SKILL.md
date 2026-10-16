---
name: ryde-stats
description: Fetch, summarize, export, or map an authorized Ryde account's ride history using the Ryde CLI or MCP server. Use when the user asks for their Ryde rides, RidePass analysis, or local stats dashboard.
license: MIT
---

Use the Ryde MCP tools when connected. Otherwise use the CLI through uv.
In this repository use `uv run ryde`; elsewhere use
`uvx --from ryde-cli ryde`.
Run `--help` for exact options.

Authentication belongs to the user. If no session exists, explain that they
need to run the login command interactively. Do not ask them to paste tokens,
SMS codes, or config contents into chat. Do not trigger another SMS unless the
user requested it. Existing authorization to fetch or map their rides is enough
to continue; do not repeatedly ask for the same permission.

For “fetch all my data and show stats,” fetch the dashboard's completed ride
history and, if the user requested precise routes, include route traces. This
workflow does not export unrelated profile or payment data. Standard ride
records may already contain start/end coordinates and addresses.

- CLI: `uv run ryde stats --include-location --no-open` (omit
  `--include-location` unless precise route retrieval is authorized). Return the
  resulting `url`; browser opening is optional. `--fetch-only` saves without a
  server; `--no-fetch` serves the previous dataset without API requests.
- MCP: call `open_stats` with `include_sensitive_location` matching the user's
  request. It returns a `job_id` immediately. Poll `stats_job_status` until
  `completed` or `failed`; return the completed result's `url` and counts.
  `prepare_stats` starts an export without opening a server. Do not repeatedly
  start jobs while an existing job is running. `open_stats(refresh=false)`
  opens a prepared dataset immediately.
- Summaries and pass comparisons: use `ride_summary` / `recommend_ridepass`, or
  the CLI's `summary` / `optimize --city-id CITY_ID`. Explain that the pass model
  uses current prices and assumptions, not guaranteed savings.

Export data stays in the account-scoped private data directory outside the
repository. Never copy personal datasets, auth files, or live output into a
commit, fixture, skill, or public artifact. Do not echo tokens in tool results.

Dashboard URLs are temporary local access capabilities: share only with the
requesting user, never publish or log them. The server binds to `127.0.0.1` and
expires after one hour by default. Use `close_stats(url)` or
`uv run ryde stats --stop '<dashboard-url>'` when finished. Stopping the server
does not delete cached data. The dashboard loads public map tiles externally.

Local URLs work only on the machine running the CLI/MCP process. A remote agent
should report that limitation and return structured summaries or exports; it
must not claim the user's laptop can open the remote loopback URL. Do not
create a public tunnel without an explicit request.
