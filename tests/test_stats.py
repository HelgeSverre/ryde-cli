import json
import threading
import urllib.error
import urllib.request

import pytest

from ryde_cli.client import RydeError
from ryde_cli.config import ConfigStore, secure_write_json
from ryde_cli.dashboard_server import close_dashboard, make_server
from ryde_cli.stats import dataset_path, prepare_stats, without_credentials


class SyntheticClient:
    token = "synthetic-session-secret"

    def __init__(self):
        self.calls = []

    def rides(self, start=None, end=None):
        return [
            {
                "useId": "synthetic-1",
                "startTime": "2026-01-01 12:00:00",
                "endTime": "2026-01-01 12:10:00",
                "startGps": "10,20",
                "endGps": "10.01,20.01",
                "token": self.token,
                "nested": {"access_token": self.token, "safe": "test"},
            }
        ]

    def route(self, use_id):
        self.calls.append(use_id)
        return {
            "locus": [{"gpsAddress": "10,20"}, {"gpsAddress": "10.01,20.01"}],
            "token": self.token,
        }


def read_manifest(directory):
    return json.loads((directory / "manifest.json").read_text())


def test_prepare_requires_no_route_requests_by_default_and_strips_credentials(tmp_path):
    client = SyntheticClient()
    result = prepare_stats(client, tmp_path)
    assert client.calls == []
    assert result["counts"] == {"rides": 1, "complete": 0, "missing": 0, "failed": 0}
    manifest = read_manifest(tmp_path)
    content = (tmp_path / manifest["rideFile"]).read_text()
    assert client.token not in content
    assert "access_token" not in content
    assert '"token"' not in content
    assert json.loads(content)["rides"][0]["startGps"] == "10,20"
    for path in tmp_path.glob("*.json"):
        assert path.stat().st_mode & 0o777 == 0o600
    assert tmp_path.stat().st_mode & 0o777 == 0o700


def test_route_cache_resumes_and_manifest_selects_current_rides_only(tmp_path):
    client = SyntheticClient()
    first = prepare_stats(client, tmp_path, include_location=True)
    assert first["counts"]["complete"] == 1
    previous = read_manifest(tmp_path)
    second = prepare_stats(client, tmp_path, include_location=True)
    assert client.calls == ["synthetic-1"]
    assert second["counts"]["complete"] == 1
    assert read_manifest(tmp_path)["rideFile"] != previous["rideFile"]
    assert (tmp_path / previous["rideFile"]).exists()
    client.rides = lambda *a: []
    assert prepare_stats(client, tmp_path, include_location=True)["counts"]["rides"] == 0
    assert read_manifest(tmp_path)["routeFiles"] == []


def test_failed_routes_can_be_retried(tmp_path):
    client = SyntheticClient()
    original = client.route
    client.route = lambda _: (_ for _ in ()).throw(RydeError("temporary network failure"))
    assert prepare_stats(client, tmp_path, include_location=True)["counts"]["failed"] == 1
    client.route = original
    assert prepare_stats(client, tmp_path, include_location=True)["counts"]["complete"] == 1


def test_same_directory_cannot_mix_logins(tmp_path):
    client = SyntheticClient()
    prepare_stats(client, tmp_path)
    client.token = "different-synthetic-session"
    with pytest.raises(RydeError, match="another login"):
        prepare_stats(client, tmp_path)


def test_default_data_directory_is_scoped_to_config_and_token(tmp_path):
    store = ConfigStore(str(tmp_path / "profile.json"))
    one = dataset_path(store, "first-synthetic-token")
    assert one != dataset_path(store, "second-synthetic-token")
    assert one != dataset_path(ConfigStore(str(tmp_path / "other.json")), "first-synthetic-token")
    assert "first-synthetic-token" not in str(one)


def test_redaction_removes_nested_credentials_and_echoed_token():
    assert without_credentials(
        {"sessionToken": "fake", "rows": [{"text": "echo fake-token"}]}, "fake-token"
    ) == {"rows": [{"text": "echo [redacted]"}]}


def test_server_only_serves_snapshot_files_and_bundle(tmp_path):
    prepare_stats(SyntheticClient(), tmp_path, include_location=True)
    server, url = make_server(tmp_path)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(url) as response:
            assert b"<html" in response.read()
            assert response.headers["Referrer-Policy"] == "no-referrer"
            assert response.headers["Cache-Control"] == "no-store"
        with opener.open(url + "data/manifest.json") as response:
            manifest = json.load(response)
        with opener.open(url + "data/" + manifest["rideFile"]) as response:
            assert "synthetic-session-secret" not in response.read().decode()
        for path in [
            "data/.owner.json",
            "data/.routes/x.json",
            "data/config.json",
            "../config.json",
            "%2e%2e/config.json",
        ]:
            with pytest.raises(urllib.error.HTTPError) as error:
                opener.open(url + path)
            assert error.value.code == 404
        with pytest.raises(urllib.error.HTTPError):
            opener.open(url.split(url.split("/")[-2])[0])
        request = urllib.request.Request(url, headers={"Host": "attacker.example"})
        with pytest.raises(urllib.error.HTTPError):
            opener.open(request)
        original_manifest = manifest
        prepare_stats(SyntheticClient(), tmp_path)
        with opener.open(url + "data/manifest.json") as response:
            assert json.load(response) == original_manifest
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_manifest_rejects_traversal_and_symlinks(tmp_path):
    secure_write_json(tmp_path / "manifest.json", {"rideFile": "../config.json", "routeFiles": []})
    with pytest.raises(RydeError, match="filenames"):
        make_server(tmp_path)
    secure_write_json(tmp_path / "manifest.json", {"rideFile": "config.json", "routeFiles": []})
    with pytest.raises(RydeError, match="filenames"):
        make_server(tmp_path)


@pytest.mark.parametrize(
    "url",
    ["https://example.com/", "http://localhost:8000/foo/", "http://127.0.0.1:8000/not-a-session/"],
)
def test_shutdown_rejects_arbitrary_urls(url):
    with pytest.raises(RydeError, match="exact local dashboard URL"):
        close_dashboard(url)
