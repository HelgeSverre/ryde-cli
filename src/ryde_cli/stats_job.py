"""Durable background stats jobs for MCP clients with short tool timeouts."""

from __future__ import annotations

import argparse
import datetime as dt
import os
import re
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Any

from .client import RydeClient, RydeError
from .config import ConfigStore, secure_read_json, secure_write_json
from .stats import dataset_path, open_dashboard, prepare_stats


def status_path(directory: Path, job_id: str) -> Path:
    if not re.fullmatch(r"[a-f0-9]{32}", job_id):
        raise RydeError("invalid stats job ID")
    return directory / ".jobs" / f"{job_id}.json"


def job_status(directory: Path, job_id: str) -> dict[str, Any]:
    result = secure_read_json(status_path(directory, job_id))
    if not result:
        raise RydeError("stats job not found for this login")
    return result


def start_job(
    config: ConfigStore,
    *,
    include_location: bool = False,
    start: str | None = None,
    end: str | None = None,
    open_when_ready: bool = False,
    open_browser: bool = False,
    ttl: int = 3600,
) -> dict[str, Any]:
    if not config.token():
        raise RydeError("log in with uv run ryde login before preparing stats")
    for value in (start, end):
        if value:
            dt.date.fromisoformat(value)
    if not 1 <= ttl <= 86400:
        raise RydeError("ttl must be 1–86400 seconds")
    directory = dataset_path(config, config.token())
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(directory, 0o700)
    job_id = uuid.uuid4().hex
    status = status_path(directory, job_id)
    status.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    result = {"job_id": job_id, "state": "queued"}
    secure_write_json(status, result)
    command = [
        sys.executable,
        "-m",
        "ryde_cli.stats_job",
        "--config",
        str(config.path.resolve()),
        "--job-id",
        job_id,
        "--ttl",
        str(ttl),
    ]
    for flag, value in (("--start", start), ("--end", end)):
        if value:
            command.extend([flag, value])
    if include_location:
        command.append("--include-location")
    if open_when_ready:
        command.append("--open")
    if open_browser:
        command.append("--browser")
    subprocess.Popen(
        command,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True)
    parser.add_argument("--job-id", required=True)
    parser.add_argument("--include-location", action="store_true")
    parser.add_argument("--start")
    parser.add_argument("--end")
    parser.add_argument("--ttl", type=int, default=3600)
    parser.add_argument("--open", action="store_true")
    parser.add_argument("--browser", action="store_true")
    args = parser.parse_args()
    config = ConfigStore(args.config)
    token = config.token()
    directory = dataset_path(config, token)
    path = status_path(directory, args.job_id)
    secure_write_json(path, {"job_id": args.job_id, "state": "running"})
    stage = "fetch"
    try:
        client = RydeClient(
            token=token, base_url=config.base_url(), mobile_type=config.mobile_type()
        )
        result = prepare_stats(
            client,
            directory,
            start=dt.date.fromisoformat(args.start) if args.start else None,
            end=dt.date.fromisoformat(args.end) if args.end else None,
            include_location=args.include_location,
        )
        if args.open:
            stage = "dashboard"
            result.update(open_dashboard(directory, ttl=args.ttl, open_browser=args.browser))
        secure_write_json(path, {"job_id": args.job_id, "state": "completed", **result})
    except Exception as exc:
        # Neither raw exception bodies nor account tokens belong in agent results.
        secure_write_json(
            path,
            {
                "job_id": args.job_id,
                "state": "failed",
                "stage": stage,
                "error_type": type(exc).__name__,
                "error": "Stats preparation failed. Check authentication and network access, then retry; cached routes are retained.",
            },
        )


if __name__ == "__main__":
    main()
