import json

import pytest

from ryde_cli import __version__
from ryde_cli.cli import build_parser, main, normalize_parent_options, render


def test_version_does_not_require_login(capsys):
    with pytest.raises(SystemExit) as result:
        main(["--version"])
    assert result.value.code == 0
    assert capsys.readouterr().out.strip() == f"ryde {__version__}"


@pytest.mark.parametrize(
    "argv",
    [
        ["rides", "list", "--format", "csv", "--config", "/tmp/unused"],
        ["--config", "/tmp/unused", "rides", "--format", "csv", "list"],
    ],
)
def test_common_options_after_nested_commands(argv):
    args = build_parser().parse_args(normalize_parent_options(argv))
    assert args.config == "/tmp/unused"
    assert args.format == "csv"
    assert args.rides_command == "list"


def test_route_requires_explicit_location_acknowledgement(monkeypatch, capsys):
    class Client:
        def route(self, _):
            pytest.fail("Location request must not happen without consent")

    monkeypatch.setattr("ryde_cli.cli.client_from", lambda _: (Client(), None))
    with pytest.raises(SystemExit) as result:
        main(["rides", "route", "synthetic-ride"])
    assert result.value.code == 1
    assert "--include-location" in capsys.readouterr().err


def test_json_export_preserves_lists_and_owner_only_permissions(tmp_path, capsys):
    path = tmp_path / "export.json"
    render([{"id": "synthetic"}], "json", str(path))
    assert json.loads(path.read_text()) == [{"id": "synthetic"}]
    assert path.stat().st_mode & 0o777 == 0o600
    output = capsys.readouterr()
    assert not output.out
    assert "Wrote" in output.err


@pytest.mark.parametrize("fmt", ["json", "csv", "tsv", "table"])
def test_export_write_failures_have_cli_errors(tmp_path, monkeypatch, capsys, fmt):
    class Client:
        def profile(self):
            return {"id": "synthetic"}

    blocker = tmp_path / "file"
    blocker.write_text("existing file")
    monkeypatch.setattr("ryde_cli.cli.client_from", lambda _: (Client(), None))
    with pytest.raises(SystemExit) as result:
        main(["account", "profile", "--format", fmt, "--output", str(blocker / "export")])
    assert result.value.code == 1
    assert "error: could not write file" in capsys.readouterr().err
    assert blocker.read_text() == "existing file"


def test_skill_parent_file_has_a_cli_error(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".agents").write_text("existing file")
    with pytest.raises(SystemExit) as result:
        main(["skill", "--agent", "codex"])
    assert result.value.code == 1
    assert "could not install skill" in capsys.readouterr().err


def test_stats_fetch_only_does_not_launch_server(monkeypatch, tmp_path, capsys):
    from ryde_cli.client import RydeClient
    from ryde_cli.config import ConfigStore

    client = RydeClient(token="synthetic-token")
    monkeypatch.setattr("ryde_cli.cli.client_from", lambda _: (client, ConfigStore()))
    monkeypatch.setattr("ryde_cli.stats.prepare_stats", lambda *a, **kw: {"counts": {"rides": 3}})
    monkeypatch.setattr(
        "ryde_cli.stats.open_dashboard", lambda *a, **kw: pytest.fail("No server expected")
    )
    main(["stats", "--data-dir", str(tmp_path), "--fetch-only"])
    assert json.loads(capsys.readouterr().out)["counts"]["rides"] == 3


def test_cli_exposes_readonly_groups() -> None:
    parser = build_parser()
    assert parser.parse_args(["--config", "/tmp/c", "rides", "list"])
    assert parser.parse_args(["passes", "catalogue", "--city-id", "15"])
    assert parser.parse_args(["payments", "vipps", "--all"])
    assert parser.parse_args(["fees", "--city-id", "15"])
    assert parser.parse_args(["export", "rides", "--format", "csv"])
    assert parser.parse_args(["cities", "sample"])


def test_city_lookup_and_export(monkeypatch, tmp_path, capsys):
    class Client:
        def cities(self, query):
            assert query in {"sample", None}
            return [{"cityId": 101, "cityName": "Sample City"}]

    monkeypatch.setattr("ryde_cli.cli.client_from", lambda _: (Client(), None))
    main(["cities", "sample"])
    assert json.loads(capsys.readouterr().out)[0]["cityId"] == 101
    path = tmp_path / "cities.json"
    main(["export", "cities", "--output", str(path)])
    assert json.loads(path.read_text())[0]["cityName"] == "Sample City"


@pytest.mark.parametrize("resource", ["catalogue", "fee-rule", "recommendation"])
def test_city_exports_require_explicit_id(resource, monkeypatch, capsys):
    monkeypatch.setattr(
        "ryde_cli.cli.client_from", lambda _: pytest.fail("No API request expected")
    )
    with pytest.raises(SystemExit) as result:
        main(["export", resource])
    assert result.value.code == 1
    assert "--city-id is required" in capsys.readouterr().err


@pytest.mark.parametrize("challenge", [{"reCAPTCHA": "1"}, {"isImgCode": "1"}, {"reCAPTCHA": "0"}])
def test_login_stops_before_sms_when_android_challenge_required(challenge, monkeypatch, capsys):
    class Client:
        def check_phone(self, *args):
            return {"status": 200}

        def phone_code_options(self, phone, country_code, device):
            assert device == "synthetic-device"
            return challenge

        def request_sms(self, *args):
            pytest.fail("Cannot send SMS without completing the required challenge")

        def attestation_challenge(self, phone, device, purpose):
            assert purpose == "send_sms"
            return {"challengeId": "synthetic-challenge", "challenge": "synthetic-proof-input"}

    class Store:
        data = {}

        def device_id(self):
            return "synthetic-device"

    monkeypatch.setattr("ryde_cli.cli.client_from", lambda *a, **kw: (Client(), Store()))
    with pytest.raises(SystemExit) as result:
        main(["login", "--phone", "+4791234567", "--send-sms"])
    assert result.value.code == 1
    assert "challenge" in capsys.readouterr().err


def test_failed_sms_attempt_preserves_device_and_duplicate_guard(monkeypatch, capsys):
    from ryde_cli.client import RydeError
    from ryde_cli.config import ConfigStore

    store = ConfigStore()

    class Client:
        def check_phone(self, *args):
            return {"status": 200}

        def phone_code_options(self, *args):
            return {"reCAPTCHA": "0", "attemptId": "synthetic-attempt"}

        def attestation_challenge(self, *args):
            return {"status": 200}

        def request_sms(self, phone, country_code, device, attempt_id):
            saved = ConfigStore()
            assert saved.data["device_id"] == device
            assert saved.data["last_sms_at"] > 0
            assert attempt_id == "synthetic-attempt"
            raise RydeError("synthetic SMS rejection")

    monkeypatch.setattr("ryde_cli.cli.client_from", lambda *a, **kw: (Client(), store))
    for expected in ["synthetic SMS rejection", "refusing a duplicate"]:
        with pytest.raises(SystemExit):
            main(["login", "--phone", "+4791234567", "--send-sms"])
        assert expected in capsys.readouterr().err
