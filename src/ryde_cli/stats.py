"""Fetch a resumable, account-scoped dataset for the bundled local dashboard."""

from __future__ import annotations

import datetime as dt
import fcntl
import hashlib
import json
import os
import select
import subprocess
import sys
import webbrowser
from pathlib import Path
from typing import Any

from .client import AuthenticationRequired, RydeClient, RydeError
from .config import ConfigStore, secure_read_json, secure_write_json

_SENSITIVE_KEYS = {
    "token",
    "authorization",
    "password",
    "secret",
    "cookie",
    "smscode",
    "userdevice",
    "deviceid",
}


def without_credentials(value: Any, token: str = "") -> Any:
    if isinstance(value, dict):
        return {
            key: without_credentials(item, token)
            for key, item in value.items()
            if not any(
                part in key.lower().replace("_", "").replace("-", "") for part in _SENSITIVE_KEYS
            )
        }
    if isinstance(value, list):
        return [without_credentials(item, token) for item in value]
    return value.replace(token, "[redacted]") if token and isinstance(value, str) else value


def dataset_path(store: ConfigStore, token: str, override: str | None = None) -> Path:
    if override:
        return Path(override).expanduser().resolve()
    if not token:
        raise AuthenticationRequired(
            "log in with uv run ryde login, or select an offline --data-dir"
        )
    # Different configs or tokens never reuse another account's route cache.
    identity = hashlib.sha256(f"{store.path.resolve()}\0{token}".encode()).hexdigest()[:24]
    root = Path(os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local/share")))
    return root / "ryde-cli" / "stats" / identity


def prepare_stats(
    client: RydeClient,
    directory: Path,
    **kwargs: Any,
) -> dict[str, Any]:
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(directory, 0o700)
    lock_fd = os.open(directory / ".fetch.lock", os.O_CREAT | os.O_RDWR, 0o600)
    with os.fdopen(lock_fd, "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        return _prepare_stats(client, directory, **kwargs)


def _prepare_stats(
    client: RydeClient,
    directory: Path,
    *,
    start: dt.date | None = None,
    end: dt.date | None = None,
    include_location: bool = False,
) -> dict[str, Any]:
    """Fetch ride records and optionally route traces; never export credentials."""
    if not client.token:
        raise AuthenticationRequired("log in first with uv run ryde login")
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(directory, 0o700)
    # Bind custom directories too: changing accounts must not mix cached traces.
    owner = hashlib.sha256(client.token.encode()).hexdigest()
    identity_file = directory / ".owner.json"
    identity = secure_read_json(identity_file)
    if identity and identity.get("fingerprint") != owner:
        raise RydeError("stats directory belongs to another login; choose a different --data-dir")
    secure_write_json(identity_file, {"fingerprint": owner})
    rides = without_credentials(client.rides(start, end), client.token)
    cache_dir = directory / ".routes"
    cache_dir.mkdir(exist_ok=True, mode=0o700)
    os.chmod(cache_dir, 0o700)
    years: dict[str, dict[str, Any]] = {}
    counts = {"rides": len(rides), "complete": 0, "missing": 0, "failed": 0}
    for ride in rides:
        use_id = ride.get("useId")
        if use_id is None or not include_location:
            continue
        use_id = str(use_id)
        year_text = str(ride.get("startTime", ""))[:4]
        year = year_text if year_text.isdigit() and len(year_text) == 4 else "unknown"
        cache_file = cache_dir / f"{hashlib.sha256(use_id.encode()).hexdigest()}.json"
        item = secure_read_json(cache_file)
        if not item or item.get("status") == "failed":
            try:
                response = without_credentials(client.route(use_id), client.token)
                locus = response.get("locus")
                status = "complete" if isinstance(locus, list) and locus else "missing"
                item = {
                    "useId": use_id,
                    "year": year,
                    "status": status,
                    "response": {"locus": locus if isinstance(locus, list) else []},
                }
            except RydeError as exc:
                # Abort expired sessions rather than issuing requests for every ride.
                if "401" in str(exc) or "token" in str(exc).lower():
                    raise RydeError("stats fetch could not authenticate; log in again") from None
                item = {"useId": use_id, "year": year, "status": "failed"}
            secure_write_json(cache_file, item)
        counts[item["status"]] += 1
        years.setdefault(year, {})[use_id] = item
    # Versioned immutable files keep an existing dashboard session consistent
    # during a refresh. The manifest switches only after every file is ready.
    generation = dt.datetime.now(dt.UTC).strftime("%Y%m%dT%H%M%S%f")
    ride_filename = f"rides-{generation}.raw.json"
    secure_write_json(directory / ride_filename, {"rides": rides})
    route_files = []
    for year, entries in sorted(years.items()):
        filename = f"routes-{year}-{generation}.raw.json"
        secure_write_json(directory / filename, {"year": year, "routes": entries})
        route_files.append({"year": year, "file": filename, "count": len(entries)})
    manifest = {
        "version": 1,
        "exportedAt": dt.datetime.now(dt.UTC).isoformat(),
        "rideFile": ride_filename,
        "routeFiles": route_files,
        "counts": counts,
    }
    secure_write_json(directory / "manifest.json", manifest)
    return {"data_dir": str(directory), "counts": counts, "includes_route_traces": include_location}


def open_dashboard(
    directory: Path, *, port: int = 0, ttl: int = 3600, open_browser: bool = False
) -> dict[str, Any]:
    if not 0 <= port <= 65535 or not 1 <= ttl <= 86400:
        raise RydeError("port must be 0–65535 and ttl must be 1–86400 seconds")
    if not (directory / "manifest.json").is_file():
        raise RydeError("no stats dataset found; fetch data before opening the dashboard")
    child = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "ryde_cli.dashboard_server",
            "--data-dir",
            str(directory),
            "--port",
            str(port),
            "--ttl",
            str(ttl),
        ],
        env={key: value for key, value in os.environ.items() if not key.startswith("RYDE_")},
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
        text=True,
    )
    assert child.stdout is not None
    try:
        readable, _, _ = select.select([child.stdout], [], [], 30)
        if not readable:
            child.terminate()
            raise RydeError("dashboard server did not start within 30 seconds")
        line = child.stdout.readline()
        if not line:
            raise RydeError("dashboard server could not start; check the data directory and port")
        result = json.loads(line)
    finally:
        child.stdout.close()
    if open_browser:
        result["browser_opened"] = webbrowser.open(result["url"])
    return result
