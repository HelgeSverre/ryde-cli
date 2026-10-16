import json
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from ryde_cli.client import RydeError
from ryde_cli.config import ConfigStore
from ryde_cli.dashboard_server import close_dashboard
from ryde_cli.stats import dataset_path
from ryde_cli.stats_job import job_status, start_job


def test_background_fetch_open_and_stop_use_synthetic_loopback_api(tmp_path, monkeypatch):
    class Api(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            self.rfile.read(int(self.headers["Content-Length"]))
            if self.path.endswith("getUserAllUseLog"):
                value = {
                    "userUses": [
                        {
                            "useId": "synthetic-job",
                            "startTime": "2026-01-01 12:00:00",
                            "startGps": "10,20",
                            "endGps": "10.01,20.01",
                        }
                    ]
                }
            elif self.path.endswith("getLocusByUseId"):
                value = {"locus": [{"gpsAddress": "10,20"}, {"gpsAddress": "10.01,20.01"}]}
            else:
                raise AssertionError("Unexpected API endpoint")
            body = json.dumps(value).encode()
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    api = ThreadingHTTPServer(("127.0.0.1", 0), Api)
    thread = threading.Thread(target=api.serve_forever, daemon=True)
    thread.start()
    store = ConfigStore(str(tmp_path / "config.json"))
    store.data = {
        "token": "synthetic-job-token",
        "base_url": f"http://127.0.0.1:{api.server_port}/",
    }
    store.save()
    # Ensure HTTP proxy configuration cannot redirect this fixture elsewhere.
    monkeypatch.setenv("NO_PROXY", "127.0.0.1")
    url = None
    try:
        started = start_job(
            store,
            include_location=True,
            start="2026-01-01",
            end="2026-01-02",
            open_when_ready=True,
            ttl=30,
        )
        assert started["state"] == "queued"
        directory = dataset_path(store, store.token())
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            status = job_status(directory, started["job_id"])
            if status["state"] in {"failed", "completed"}:
                break
            time.sleep(0.05)
        assert status["state"] == "completed", status
        assert status["counts"] == {"rides": 1, "complete": 1, "missing": 0, "failed": 0}
        assert store.token() not in json.dumps(status)
        url = status["url"]
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(url + "data/manifest.json") as response:
            assert json.load(response)["counts"]["complete"] == 1
        assert close_dashboard(url) == {"stopped": True}
        url = None
    finally:
        if url:
            close_dashboard(url)
        api.shutdown()
        api.server_close()
        thread.join(timeout=2)


def test_job_requires_auth_and_rejects_path_traversal(tmp_path):
    with pytest.raises(RydeError, match="log in"):
        start_job(ConfigStore())
    with pytest.raises(RydeError, match="invalid"):
        job_status(tmp_path, "../config")
