import base64
import datetime as dt
import io

import pytest

from ryde_cli.analysis import recommend_passes, summarize_rides
from ryde_cli.client import RydeError, aes_base64, normalise_phone, time_sign


@pytest.mark.parametrize("body", [b"synthetic-private-data", b"\xffsynthetic-private-data"])
def test_invalid_api_json_has_a_safe_error(monkeypatch, body):
    from ryde_cli.client import RydeClient

    monkeypatch.setattr("urllib.request.urlopen", lambda *a, **kw: io.BytesIO(body))
    with pytest.raises(RydeError, match="invalid JSON") as result:
        RydeClient(token="synthetic-token").profile()
    assert "synthetic-private-data" not in str(result.value)


@pytest.mark.parametrize("failure", [TimeoutError(), ConnectionResetError()])
def test_api_response_read_failures_have_domain_errors(monkeypatch, failure):
    from ryde_cli.client import RydeClient

    class FailingResponse(io.BytesIO):
        def read(self, *args):
            raise failure

    monkeypatch.setattr("urllib.request.urlopen", lambda *a, **kw: FailingResponse())
    with pytest.raises(RydeError, match="timed out|could not read the API response"):
        RydeClient(token="synthetic-token").profile()


def test_ride_history_fetches_older_archives_paginates_and_deduplicates(monkeypatch):
    from ryde_cli.client import RydeClient

    calls = []
    first_page = [
        {"useId": str(index), "startTime": f"2019-01-01 10:{index:02}:00"} for index in range(15)
    ]

    def post(self, path, fields):
        calls.append((fields["year"], fields["num"]))
        if (fields["year"], fields["num"]) == (2019, 0):
            return {"userUses": first_page}
        if (fields["year"], fields["num"]) == (2019, 1):
            return {
                "userUses": [
                    {**first_page[0], "paidNum": "100"},
                    {"useId": "older", "startTime": "2018-12-31 10:00:00"},
                ]
            }
        return {"userUses": []}

    monkeypatch.setattr(RydeClient, "post", post)
    rides = RydeClient(token="synthetic").rides(dt.date(2019, 1, 1), dt.date(2020, 1, 1))
    assert calls == [(2019, 0), (2019, 1), (2020, 0)]
    assert len(rides) == 15
    assert rides[0]["paidNum"] == "100"


def test_future_end_date_does_not_fetch_future_year_partitions(monkeypatch):
    from ryde_cli.client import RydeClient

    today = dt.date.today()
    calls = []

    def post(self, path, fields):
        calls.append(fields["year"])
        return {"userUses": []}

    monkeypatch.setattr(RydeClient, "post", post)
    client = RydeClient(token="synthetic")
    assert client.rides(dt.date(today.year, 1, 1), dt.date(today.year + 2, 1, 1)) == []
    assert calls == [""]
    calls.clear()
    assert client.rides(dt.date(today.year + 1, 1, 1), dt.date(today.year + 2, 1, 1)) == []
    assert calls == []


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
    assert request.full_url == "https://api.ryde.vip/appRyde/getUserInfoByToken"
    headers = {name.lower(): value for name, value in request.header_items()}
    assert headers["ryde-app-version"] == "6.0.0"
    assert headers["ryde-app-build"] == "715"
    assert headers["user-agent"] == "Ryde/6.0.0 Android"
    assert "appversion" not in headers


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


def test_city_lookup_filters_deduplicates_and_omits_boundaries(monkeypatch):
    from ryde_cli.client import RydeClient

    def post(self, path, fields):
        assert path == "/appRyde/getCityFences"
        assert fields == {"gpsLa": 0, "gpsLo": 0, "userCityId": ""}
        return {
            "citys": [
                {"cityId": 102, "cityName": "Sample Bay", "cityRange": "omitted"},
                {"cityId": "101", "cityName": "Sample City"},
                {"cityId": 101, "cityName": "Sample City"},
                {"cityId": 103, "cityName": "Elsewhere"},
                {"cityId": "invalid", "cityName": "Sample"},
                None,
            ],
            "fences": [{"synthetic": "boundary"}],
        }

    monkeypatch.setattr(RydeClient, "post", post)
    client = RydeClient(token="synthetic")
    assert client.cities("SAMPLE") == [
        {"cityId": 102, "cityName": "Sample Bay"},
        {"cityId": 101, "cityName": "Sample City"},
    ]
    assert len(client.cities()) == 3
    assert client.cities("missing") == []


def test_city_lookup_rejects_missing_city_list(monkeypatch):
    from ryde_cli.client import RydeClient

    monkeypatch.setattr(RydeClient, "post", lambda *a, **kw: {"status": 200})
    with pytest.raises(RydeError, match="citys list"):
        RydeClient(token="synthetic").cities()


def test_sms_preflight_and_request_share_device_and_attempt(monkeypatch):
    import hashlib

    from ryde_cli.client import RydeClient

    calls = []

    def post(self, path, fields, *, auth):
        assert not auth
        calls.append((path, fields))
        return {"status": 200, "attemptId": "synthetic-attempt"}

    monkeypatch.setattr(RydeClient, "post", post)
    client = RydeClient()
    phone = "+4791234567"
    options = client.phone_code_options(phone, "+47", "synthetic-device")
    client.request_sms(phone, "+47", "synthetic-device", options["attemptId"])
    assert calls[0][1]["userDevice"] == calls[1][1]["userDevice"] == "synthetic-device"
    assert calls[1][1]["attemptId"] == "synthetic-attempt"
    assert calls[1][1]["phoneHash"] == hashlib.sha256(phone.encode()).hexdigest()


def test_missing_auth_does_not_make_requests(monkeypatch):
    from ryde_cli.client import AuthenticationRequired, RydeClient

    monkeypatch.setattr(
        "urllib.request.urlopen", lambda *a, **kw: pytest.fail("No request expected")
    )
    with pytest.raises(AuthenticationRequired):
        RydeClient().profile()
