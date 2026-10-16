"""Small, dependency-light client for verified, read-only Ryde endpoints.

The API is private/undocumented. This module deliberately exposes no endpoint
that starts, unlocks, pays for, edits, or otherwise changes anything.
"""

from __future__ import annotations

import base64
import datetime as dt
import hashlib
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.padding import PKCS7

from .config import DEFAULT_BASE_URL, DEFAULT_MOBILE_TYPE

_KEY = b"d5pfboziywpiinym"
_IV = b"ji74d7vv2oalj4nz"
APP_VERSION = "6.0.0"
APP_BUILD = "715"
USER_AGENT = f"Ryde/{APP_VERSION} Android"


class RydeError(RuntimeError):
    """A request failed without exposing credentials."""


class AuthenticationRequired(RydeError):
    """An operation needs a saved token."""


def aes_base64(value: str) -> str:
    """Match the Android app's AES-128-CBC/PKCS#5 + Base64 signer."""
    padder = PKCS7(128).padder()
    padded = padder.update(value.encode("utf-8")) + padder.finalize()
    cipher = Cipher(algorithms.AES(_KEY), modes.CBC(_IV))
    encryptor = cipher.encryptor()
    encrypted = encryptor.update(padded) + encryptor.finalize()
    return base64.b64encode(encrypted).decode("ascii")


def time_sign(timestamp: str) -> str:
    """Return the verified request timeSign for a millisecond timestamp."""
    return hashlib.md5(aes_base64(f"rydeGood:{timestamp}:ryde-app").encode("ascii")).hexdigest()


def normalise_phone(phone: str, country_code: str = "+47") -> tuple[str, str]:
    """Normalize a user number into E.164 and app-style country-code fields.

    The app sends a full E.164 ``userPhone`` and a separate ``+<country>``
    code. Numbers without '+' are interpreted as local to ``country_code``.
    """
    compact = "".join(char for char in phone.strip() if char.isdigit() or char == "+")
    prefix = "+" + "".join(char for char in country_code if char.isdigit())
    if not prefix[1:]:
        raise RydeError("country code must contain digits")
    if compact.startswith("00"):
        compact = "+" + compact[2:]
    if compact.startswith("+"):
        digits = compact[1:]
    else:
        digits = prefix[1:] + compact.lstrip("0")
    if not digits.isdigit() or not 7 <= len(digits) <= 15:
        raise RydeError("phone number must be a plausible local or E.164 number")
    return "+" + digits, prefix


@dataclass(slots=True)
class RydeClient:
    """Authenticated API client limited to account-data endpoints."""

    token: str = ""
    base_url: str = DEFAULT_BASE_URL
    mobile_type: str = DEFAULT_MOBILE_TYPE
    timeout: float = 30.0

    def __post_init__(self) -> None:
        if not self.base_url.endswith("/"):
            self.base_url += "/"

    def post(
        self, path: str, fields: dict[str, Any] | None = None, *, auth: bool = True
    ) -> dict[str, Any]:
        """POST a signed form request and return a JSON object response."""
        payload = {key: str(value) for key, value in (fields or {}).items() if value is not None}
        if auth:
            if not self.token:
                raise AuthenticationRequired("log in first (uv run ryde login) or set RYDE_TOKEN")
            payload.setdefault("token", self.token)
        timestamp = str(int(time.time() * 1000))
        payload.setdefault("timestamp", timestamp)
        payload.setdefault("timeSign", time_sign(timestamp))
        request = urllib.request.Request(
            urllib.parse.urljoin(self.base_url, path.lstrip("/")),
            data=urllib.parse.urlencode(payload).encode("utf-8"),
            method="POST",
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json",
                "Ryde-App-Version": APP_VERSION,
                "Ryde-App-Build": APP_BUILD,
                "MobileType": self.mobile_type,
                "X-Frame-Options": "DENY",
                "User-Agent": USER_AGENT,
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                data = json.load(response)
        except urllib.error.HTTPError as exc:
            # Only recognize fixed protocol codes; error bodies can echo credentials.
            try:
                error = json.loads(exc.read(65_536))
            except (ValueError, OSError):
                error = None
            code = error.get("code") if isinstance(error, dict) else None
            if code == "APP_ATTEST_INVALID":
                raise RydeError(
                    f"{path}: Ryde requires verification from its official app (APP_ATTEST_INVALID)"
                ) from None
            if code == "DPOP_REQUIRED":
                raise AuthenticationRequired(
                    f"{path}: this session requires its device-bound key; a token alone "
                    "cannot authenticate it (DPOP_REQUIRED)"
                ) from None
            if exc.code == 401:
                raise AuthenticationRequired(
                    f"{path}: session expired or invalid (HTTP 401); log in again"
                ) from None
            raise RydeError(f"{path}: server rejected request (HTTP {exc.code})") from None
        except urllib.error.URLError as exc:
            raise RydeError(f"{path}: network error: {exc.reason}") from exc
        except TimeoutError:
            raise RydeError(f"{path}: network request timed out") from None
        except OSError as exc:
            raise RydeError(f"{path}: could not read the API response") from exc
        except (json.JSONDecodeError, UnicodeDecodeError):
            raise RydeError(f"{path}: server returned invalid JSON") from None
        if not isinstance(data, dict):
            raise RydeError(f"{path}: expected a JSON object")
        if data.get("tokenStatus") in (1, "1") or data.get("status") in (401, "401"):
            raise AuthenticationRequired(f"{path}: session expired or invalid; log in again")
        status = data.get("status")
        if status not in (None, 200, "OK"):
            message = str(data.get("message") or data.get("error") or "unknown API error")
            if self.token:
                message = message.replace(self.token, "[redacted]")
            raise RydeError(f"{path}: API status {status}: {message}")
        return data

    # Login preflight/request methods are the only unauthenticated calls. They
    # can trigger an SMS only through request_sms(), which CLI rate-limits.
    def check_phone(self, phone: str, country_code: str, device_id: str) -> dict[str, Any]:
        return self.post(
            "/appRyde/checkUserPhone",
            {
                "userPhone": phone,
                "countryCode": country_code,
                "googleId": "",
                "userDevice": device_id,
            },
            auth=False,
        )

    def phone_code_options(
        self, phone: str, country_code: str, device_id: str | None = None
    ) -> dict[str, Any]:
        return self.post(
            "/appRyde/getPhoneCode",
            {
                "userPhone": phone,
                "countryCode": country_code,
                "time": "",
                "userDevice": device_id,
            },
            auth=False,
        )

    def attestation_challenge(self, phone: str, device_id: str, purpose: str) -> dict[str, Any]:
        """Check whether login needs a Google Play Integrity proof from Android."""
        return self.post(
            "/appRyde/getAttestChallenge",
            {
                "userDevice": device_id,
                "platform": "2",
                "phoneHash": hashlib.sha256(phone.encode()).hexdigest(),
                "purpose": purpose,
            },
            auth=False,
        )

    def request_sms(
        self, phone: str, country_code: str, device_id: str, attempt_id: str | None = None
    ) -> dict[str, Any]:
        return self.post(
            "/appRyde/sendSms",
            {
                "userPhone": phone,
                "imgCode": "",
                "sign": aes_base64(phone),
                "countryCode": country_code,
                "userDevice": device_id,
                "phoneHash": hashlib.sha256(phone.encode()).hexdigest(),
                "attemptId": attempt_id,
            },
            auth=False,
        )

    def login(
        self,
        phone: str,
        country_code: str,
        sms_code: str,
        device_id: str,
        phone_info: str,
        latitude: float,
        longitude: float,
    ) -> dict[str, Any]:
        return self.post(
            "/appRyde/userLogin",
            {
                "userPhone": phone,
                "smsCode": sms_code,
                "phoneInfo": phone_info,
                "gpsLa": latitude,
                "gpsLo": longitude,
                "mobileType": self.mobile_type,
                "countryCode": country_code,
                "userDevice": device_id,
                "phoneHash": hashlib.sha256(phone.encode()).hexdigest(),
            },
            auth=False,
        )

    # Verified personal/account data endpoints.
    def cities(self, query: str | None = None) -> list[dict[str, Any]]:
        """Look up available city names and IDs without requesting the user's location."""
        response = self.post(
            "/appRyde/getCityFences",
            {"gpsLa": 0, "gpsLo": 0, "userCityId": ""},
        )
        records = response.get("citys")
        if not isinstance(records, list):
            raise RydeError("city response is missing the citys list")
        cities = {}
        for record in records:
            if not isinstance(record, dict):
                continue
            name = record.get("cityName")
            try:
                city_id = int(record.get("cityId", 0))
            except (TypeError, ValueError):
                continue
            if city_id > 0 and isinstance(name, str) and name.strip():
                if query is None or query.casefold() in name.casefold():
                    cities[city_id] = {"cityId": city_id, "cityName": name}
        return sorted(
            cities.values(), key=lambda city: (city["cityName"].casefold(), city["cityId"])
        )

    def profile(self) -> dict[str, Any]:
        return self.post("/appRyde/getUserInfoByToken", {"isOpen": "0", "appVer": "1"})

    def active_ride(self) -> dict[str, Any]:
        return self.post("/appRyde/getUserUseNow", {"useId": ""})

    def ride_detail(self, use_id: int | str) -> dict[str, Any]:
        return self.post("/appRyde/getUserUseLogByUseId", {"useId": use_id})

    def ride_order(self, order_id: int | str) -> dict[str, Any]:
        """Return a completed ride's linked order/charge detail."""
        return self.post("/appRyde/getOrderInfoById", {"orderId": order_id})

    def route(self, use_id: int | str) -> dict[str, Any]:
        return self.post("/appRyde/getLocusByUseId", {"useId": use_id})

    def rides(
        self, start: dt.date | None = None, end: dt.date | None = None
    ) -> list[dict[str, Any]]:
        """Fetch archived and current ride partitions, deduplicated by useId."""
        start = start or dt.date(2018, 1, 1)
        today = dt.date.today()
        end = end or today
        if start > end:
            raise RydeError("start date must not be after end date")
        collected: list[dict[str, Any]] = []
        for year in range(start.year, min(end.year, today.year) + 1):
            page = 0
            while True:
                result = self.post(
                    "/appRyde/getUserAllUseLog",
                    {
                        "year": "" if year == today.year else year,
                        "num": page,
                        "startTime": "",
                        "endTime": "",
                        "sort": "1",
                    },
                )
                batch = result.get("userUses") or []
                if not isinstance(batch, list):
                    raise RydeError("getUserAllUseLog returned a malformed userUses field")
                collected.extend(item for item in batch if isinstance(item, dict))
                if len(batch) < 15:
                    break
                page += 1
        unique: dict[str, dict[str, Any]] = {}
        no_id: list[dict[str, Any]] = []
        for ride in collected:
            use_id = ride.get("useId")
            if use_id is None:
                no_id.append(ride)
            else:
                unique[str(use_id)] = ride
        values = list(unique.values()) + no_id

        def in_range(ride: dict[str, Any]) -> bool:
            value = str(ride.get("startTime") or "")[:10]
            try:
                return start <= dt.date.fromisoformat(value) <= end
            except ValueError:
                return True

        return sorted(
            (ride for ride in values if in_range(ride)),
            key=lambda item: str(item.get("startTime") or ""),
        )

    def pass_catalogue(self, city_id: int | str) -> dict[str, Any]:
        return self.post("/appRyde/getCityCards", {"cityId": city_id})

    def owned_passes(self) -> dict[str, Any]:
        return self.post("/appRyde/getUserCards", {"appVer": "1"})

    def recharge_history(
        self, page: int = 0, *, status: str = "4", card_id: str = ""
    ) -> dict[str, Any]:
        return self.post(
            "/appRyde/getRechargeList",
            {
                "reStatus": status,
                "num": page,
                "startTime": "",
                "endTime": "",
                # These are the values used by the app's successful-history
                # view. In particular, reType=7 rows in this result are the
                # historical RidePass purchases used by the analysis.
                "sort": "0",
                "getType": "1",
                "reType": "",
                "cardId": card_id,
            },
        )

    def recharge_detail(self, recharge_id: int | str) -> dict[str, Any]:
        return self.post("/appRyde/getRechargeById", {"rechargeId": recharge_id})

    def vipps_payments(self, page: int = 0) -> dict[str, Any]:
        return self.post(
            "/appRyde/getUserVippsOrders",
            {
                "num": page,
                "startTime": "",
                "endTime": "",
                "sort": "1",
            },
        )

    def fee_rule(self, city_id: int | str) -> dict[str, Any]:
        return self.post("/appRyde/getFeeRuleByCityId", {"cityId": city_id})

    def month_amount(self, month: str) -> dict[str, Any]:
        return self.post("/appRyde/getUserMonthAmount", {"month": month})

    def recharge_month(self, month: str) -> dict[str, Any]:
        return self.post("/appRyde/getRechargeMonth", {"month": month})

    def auto_buy(self) -> dict[str, Any]:
        return self.post("/appRyde/getUserAutoBuy", {})

    def fetch_pages(
        self, method: str, list_keys: Iterable[str], maximum_pages: int = 250
    ) -> list[dict[str, Any]]:
        """Get a known paginated history response without guessing mutations."""
        found: list[dict[str, Any]] = []
        for page in range(maximum_pages):
            if method == "recharge":
                response = self.recharge_history(page)
            elif method == "vipps":
                response = self.vipps_payments(page)
            else:
                raise ValueError("unsupported pagination method")
            batch: list[Any] = []
            for key in list_keys:
                candidate = response.get(key)
                if isinstance(candidate, list):
                    batch = candidate
                    break
            found.extend(item for item in batch if isinstance(item, dict))
            if len(batch) < 15:
                break
        return found
