import base64

import pytest

from ryde_cli.analysis import recommend_passes, summarize_rides
from ryde_cli.client import RydeError, aes_base64, normalise_phone, time_sign


def test_signing_matches_verified_live_test_vector() -> None:
    assert time_sign("1756288320000") == "6af328a18456726b45b8fdc83fee8e0a"
    assert base64.b64decode(aes_base64("+4791234567"))


def test_normalise_norwegian_local_and_e164() -> None:
    assert normalise_phone("91 23 45 67") == ("+4791234567", "+47")
    assert normalise_phone("004791234567") == ("+4791234567", "+47")
    assert normalise_phone("+47 91 23 45 67") == ("+4791234567", "+47")
    with pytest.raises(RydeError):
        normalise_phone("not a phone")


def test_summary_uses_minor_units_and_timestamps_for_minutes() -> None:
    result = summarize_rides(
        [
            {
                "paidNum": "5100",
                "payableNum": "5200",
                "useDist": "1200",
                "monType": "NOK",
                "startTime": "2026-08-01 10:00:00",
                "endTime": "2026-08-01 10:12:30",
            }
        ]
    )
    assert result["paid_total_nok"] == 51.0
    assert result["distance_km"] == 1.2
    assert result["riding_minutes"] == 12.5
    assert result["monthly"][0]["month"] == "2026-08"


def test_recommendation_has_explicitly_limited_cost_model() -> None:
    rides = [
        {"startTime": "2026-08-01 10:00:00", "endTime": "2026-08-01 11:00:00", "paidNum": "10000"}
    ]
    catalogue = {
        "cards": [
            {
                "cardName": "Day Pass",
                "cardId": 1,
                "cardType": 2,
                "totalMin": 60,
                "cardDays": 1,
                "cardAmount": "4900",
            }
        ]
    }
    fee = {"rule": {"ridingTime": 1, "openFee": 1090, "ruleFee": 250}}
    result = recommend_passes(rides, catalogue, fee)
    assert result["mixed_recommendation"]["total_nok"] == 49.0
    assert result["mixed_recommendation"]["timeline"][0]["name"] == "Day Pass"
    assert result["assumptions"]


def test_pass_crossing_allowance_charges_metered_overflow_only() -> None:
    rides = [{"startTime": "2026-08-01 10:00:00", "endTime": "2026-08-01 10:15:00"}]
    catalogue = {
        "cards": [
            {
                "cardName": "Ten minutes",
                "cardId": 1,
                "cardType": 2,
                "totalMin": 10,
                "cardDays": 1,
                "cardAmount": "1000",
            }
        ]
    }
    fee = {"rule": {"ridingTime": 1, "openFee": 1000, "ruleFee": 250}}
    plan = recommend_passes(rides, catalogue, fee)["mixed_recommendation"]
    assert plan["total_nok"] == 22.5  # 10 pass + five minute overflow, no unlock on crossing ride
    assert plan["timeline"][0]["overflow_nok"] == 12.5


def test_authenticated_form_is_signed_without_network(monkeypatch):
    import io
    import json
    import urllib.parse

    from ryde_cli.client import RydeClient

    captured = []

    def open_request(request, timeout):
        captured.append(request)
        return io.StringIO(json.dumps({"status": 200, "test": True}))

    monkeypatch.setattr("urllib.request.urlopen", open_request)
    assert RydeClient(token="synthetic-token").profile()["test"]
    request = captured[0]
    form = urllib.parse.parse_qs(request.data.decode())
    assert form["token"] == ["synthetic-token"]
    assert form["timeSign"] == [time_sign(form["timestamp"][0])]
    assert request.method == "POST"


def test_http_error_never_includes_reflected_credentials(monkeypatch):
    import io
    import urllib.error

    from ryde_cli.client import RydeClient

    def reject(request, timeout):
        raise urllib.error.HTTPError(
            request.full_url, 401, "Unauthorized", {}, io.BytesIO(b"synthetic-private-token")
        )

    monkeypatch.setattr("urllib.request.urlopen", reject)
    with pytest.raises(RydeError) as result:
        RydeClient(token="synthetic-private-token").profile()
    assert "401" in str(result.value)
    assert "synthetic-private-token" not in str(result.value)


def test_missing_auth_does_not_make_requests(monkeypatch):
    from ryde_cli.client import AuthenticationRequired, RydeClient

    monkeypatch.setattr(
        "urllib.request.urlopen", lambda *a, **kw: pytest.fail("No request expected")
    )
    with pytest.raises(AuthenticationRequired):
        RydeClient().profile()
