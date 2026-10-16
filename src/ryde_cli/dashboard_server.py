"""Serve only bundled UI and a manifest's data on a short-lived loopback URL."""

from __future__ import annotations

import argparse
import json
import mimetypes
import os
import re
import secrets
import threading
import time
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from .client import RydeError

ASSETS = Path(__file__).with_name("web")


def make_server(directory: Path, *, port: int = 0) -> tuple[ThreadingHTTPServer, str]:
    directory = directory.resolve()
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    # Snapshot manifest content; only explicitly referenced, flat JSON files
    # can be requested. Configs, checkpoints and arbitrary paths are never served.
    files = {manifest["rideFile"], *(item["file"] for item in manifest["routeFiles"])}
    if any(
        not re.fullmatch(r"(?:rides|routes)(?:-[A-Za-z0-9-]+)?(?:\.raw)?\.json", item)
        or (directory / item).is_symlink()
        for item in files
    ):
        raise RydeError("invalid stats manifest filenames")
    # Build the complete resource table before accepting HTTP requests. Request
    # text is only compared with keys; it never becomes a filesystem path or MIME.
    resources: dict[str, tuple[Path, str]] = {
        f"data/{name}": (directory / name, "application/json") for name in files
    }
    for asset in ASSETS.rglob("*"):
        if asset.is_file() and not asset.is_symlink():
            resources[asset.relative_to(ASSETS).as_posix()] = (
                asset,
                mimetypes.guess_type(asset.name)[0] or "application/octet-stream",
            )
    resources[""] = (ASSETS / "index.html", "text/html")
    prefix = f"/{secrets.token_urlsafe(24)}/"

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_: Any) -> None:
            pass  # URLs contain access capabilities; never log them.

        def end_headers(self) -> None:
            self.send_header("Cache-Control", "no-store")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("X-Frame-Options", "DENY")
            self.send_header("Cross-Origin-Resource-Policy", "same-origin")
            self.send_header("Cross-Origin-Opener-Policy", "same-origin")
            self.send_header("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
            self.send_header(
                "Content-Security-Policy",
                "default-src 'self'; script-src 'self' 'wasm-unsafe-eval'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob: https://tiles.openfreemap.org; connect-src 'self' https://tiles.openfreemap.org; worker-src 'self' blob:; font-src 'self' data:; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'none'",
            )
            super().end_headers()

        def route(self) -> str | None:
            if self.headers.get("Host") != f"127.0.0.1:{self.server.server_port}":
                return None
            path = urllib.parse.unquote(urllib.parse.urlsplit(self.path).path)
            if (
                self.headers.get("Sec-Fetch-Site") == "cross-site"
                and self.headers.get("Sec-Fetch-Mode") != "navigate"
            ):
                return None
            return path[len(prefix) :] if path.startswith(prefix) else None

        def do_GET(self) -> None:
            route = self.route()
            if route == "data/manifest.json":
                body = json.dumps(manifest).encode()
                mime = "application/json"
            elif route is not None and route in resources:
                path, mime = resources[route]
                try:
                    body = path.read_bytes()
                except OSError:
                    self.send_error(404)
                    return
            else:
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self) -> None:
            if self.route() != "shutdown" or self.headers.get("Origin"):
                self.send_error(404)
                return
            self.send_response(204)
            self.end_headers()
            threading.Thread(target=self.server.shutdown, daemon=True).start()

    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    server.daemon_threads = True
    return server, f"http://127.0.0.1:{server.server_port}{prefix}"


def close_dashboard(url: str) -> dict[str, bool]:
    if not re.fullmatch(r"http://127\.0\.0\.1:[0-9]+/[A-Za-z0-9_-]{32}/", url):
        raise RydeError("expected the exact local dashboard URL returned when opening stats")
    request = urllib.request.Request(url + "shutdown", data=b"", method="POST")
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(request, timeout=5):
        return {"stopped": True}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--ttl", type=int, default=3600)
    args = parser.parse_args()
    if not (ASSETS / "index.html").is_file():
        raise SystemExit("Bundled dashboard assets are missing")
    server, url = make_server(args.data_dir, port=args.port)
    timer = threading.Timer(args.ttl, server.shutdown)
    timer.daemon = True
    timer.start()
    print(
        json.dumps({"url": url, "pid": os.getpid(), "expires_at": time.time() + args.ttl}),
        flush=True,
    )
    try:
        server.serve_forever()
    finally:
        timer.cancel()
        server.server_close()


if __name__ == "__main__":
    main()
