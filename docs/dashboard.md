# Local dashboard workflow

The Python package includes the compiled dashboard. End users do not need Node,
Vite, a separate webapp checkout, or manual data exports.

```sh
# Authenticate once, then fetch ride history and open the map.
uv run ryde login
uv run ryde stats

# Also retrieve precise recorded GPS traces, with explicit acknowledgement.
uv run ryde stats --include-location

# Automation: return a URL without opening a browser.
uv run ryde stats --include-location --no-open

# Independent fetch and display stages.
uv run ryde stats --include-location --fetch-only
uv run ryde stats --no-fetch --no-open

# Reopen a selected local dataset without authentication or API requests.
uv run ryde stats --no-fetch --data-dir /path/to/private/stats --no-open

# Stop the server using the exact URL returned by the start command.
uv run ryde stats --stop '<dashboard-url>'
```

Outside a checkout, replace `uv run` with
`uvx --from git+https://github.com/HelgeSverre/ryde-cli`.

## What is fetched

Stats fetches completed ride history and, with `--include-location`, recorded
route traces. Standard ride records may already contain exact start/end GPS
coordinates and addresses. The trace flag controls additional route requests;
it does not make the ordinary records anonymous. Profile, pass, and payment
exports are separate commands.

Date filters are inclusive. Route results are saved after each request, so
rerunning an interrupted export reuses completed/missing traces and retries
failed requests. Missing older traces use start/end arcs on the map. If some
requests fail, their count is reported and the rest of the dashboard remains
usable. Run again to retry those requests. No SMS is sent by stats.

## Storage and access

The default dataset path is
`$XDG_DATA_HOME/ryde-cli/stats/<login-fingerprint>`, or
`~/.local/share/ryde-cli/stats/<login-fingerprint>` when XDG_DATA_HOME is unset.
The fingerprint scopes data to the selected config path and token without
including the token itself. Reauthentication may create a new dataset/cache.
A custom `--data-dir` is bound to its first login and refuses another token.

Dataset directories use `0700`; JSON files use `0600`. Auth credentials are
removed from exported records and never supplied to the frontend. The fetch
process can access the login; the dashboard process does not inherit Ryde
environment variables.

The dashboard binds only to `127.0.0.1`. Each session has a random path, serves
only the bundled UI and manifest-listed JSON, rejects unrelated host headers,
and sends no-store/no-referrer headers. The URL is an access capability: keep
it private. It expires after one hour, configurable with `--ttl` (up to one day).
`--port 0`, the default, chooses a free port. The server runs independently of
the CLI/MCP process until stopped or expired.

Stopping a server does not erase the private dataset. Refreshes keep immutable
snapshot files so existing sessions remain consistent. To remove retained data,
stop all dashboards for that dataset and delete its directory yourself. Private
caches are never a build input.

The browser fetches public map tiles from OpenFreeMap. It sends no Ryde token
or ride records there; tile requests still reveal the viewed map area to the
tile provider. There are no analytics or external font requests. Internet access
is required for the basemap; charts and loaded records remain local.

## MCP automation

1. Call `open_stats` (optionally `include_sensitive_location=true`). It returns
   `job_id` and `state: queued` immediately.
2. Poll `stats_job_status(job_id)` until `completed` or `failed`.
3. A completed fetch-and-open job returns `url`, `data_dir`, counts, server PID,
   and expiry. Give the URL to the requesting user.
4. Call `close_stats(url)` when finished, or let the session expire.

`prepare_stats` starts the same background export without a dashboard.
`open_stats(refresh=false)` opens the current dataset immediately. Browser
opening is opt-in for MCP and happens on the MCP host. Large fetches can take
minutes; poll an existing job rather than starting duplicate jobs. Concurrent
fetches to one dataset are serialized. A killed job may remain marked running;
starting a fresh job resumes its route cache.

Localhost belongs to the machine running the tools. Cloud/remote agents cannot
make that URL available in a laptop browser without a separately configured
connection. Return structured summaries when local browsing is unavailable;
there is no automatic public hosting or tunneling.

## Repository layout

```text
src/ryde_cli/              CLI, API client, MCP, data export, local server
src/ryde_cli/web/          Compiled UI and third-party notices shipped in wheels
src/ryde_cli/agent_skill/  Portable workflow skill shipped in wheels
web/                      React/TypeScript UI source and synthetic browser tests
scripts/                  Generated docs, package smoke check, public-tree check
```

Frontend development and rebuild instructions are in [web/README.md](../web/README.md).
