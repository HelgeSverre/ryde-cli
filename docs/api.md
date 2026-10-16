# API compatibility

This is an unofficial client for a private Android API. Compatibility may change.
The default API URL is `https://api.ryde.vip/`, taken from the Android app's
production build configuration.

The built-in request profile matches Android app `6.0.0` (build `715`):
`Ryde-App-Version: 6.0.0`, `Ryde-App-Build: 715`, and
`User-Agent: Ryde/6.0.0 Android`. It uses a Galaxy S21-style `MobileType`.
Login generates an Android-style device ID. The request profile is built in;
no config file is needed to set these headers.

## Login status

Live checks with the current APK profile pass `checkUserPhone` and
`getPhoneCode`. The latter currently returns `reCAPTCHA=1`, and
`getAttestChallenge` returns a device-attestation challenge for SMS delivery.
The APK uses Google's Android reCAPTCHA SDK and Play Integrity, with per-attempt
IDs and a SHA-256 hash of the E.164 number. SMS login is not currently supported
when those verifications are required. The CLI checks reCAPTCHA and device
attestation requirements before asking to send an SMS.

Loading the APK's public key with Google's web reCAPTCHA SDK returned HTTP 400
during verification. Android keys use a different integration from website keys;
they cannot simply be embedded in a localhost CAPTCHA page. See Google's
[key types](https://docs.cloud.google.com/recaptcha/docs/keys) and
[Android key configuration](https://docs.cloud.google.com/recaptcha/docs/create-key-mobile).
A browser callback needs a compatible Ryde web authentication flow, which has
not been identified. Signing into the official app does not create a CLI session.

## Request signing

The integrity field for form POSTs is:

```text
timeSign = lowercase_md5(base64(aes_128_cbc_pkcs7(
    "rydeGood:<timestamp_ms>:ryde-app",
    key="d5pfboziywpiinym", iv="ji74d7vv2oalj4nz")))
```

`sendSms` signs the E.164 phone number using the same AES/Base64 operation.
These constants reproduce the app protocol; they are not account credentials.
Signing is not a substitute for server-side access controls.

The AES constants above were read from the running 6.0.0 APK's native signer.
For `rydeGood:1756288320000:ryde-app`, both the APK and CLI produce
`Id+qXHTPbKDcF/MRFUfvTrGfPeFLth1/fYhfemJj3Sw=` and the MD5
`48f00bd5244d6bd95151d1a84c60a3e4`. Unauthenticated preflight success alone
does not verify signing compatibility.

Ryde can return HTTP 200 with `tokenStatus=1` for an expired session. The client
treats that as an authentication failure. It also recognizes
`APP_ATTEST_INVALID` (official-app verification required) and `DPOP_REQUIRED`
(the session's device-bound key is required) without displaying response bodies.

| Capability | Endpoint(s) |
| --- | --- |
| Login | `checkUserPhone`, `getPhoneCode`, `getAttestChallenge`, `sendSms`, `userLogin` |
| Profile / current ride | `getUserInfoByToken`, `getUserUseNow` |
| Rides / orders | `getUserAllUseLog`, `getUserUseLogByUseId`, `getOrderInfoById` |
| Stored GPS route | `getLocusByUseId` |
| Passes / recharge receipts | `getCityCards`, `getUserCards`, `getRechargeList`, `getRechargeById` |
| Payments / monthly amounts | `getUserVippsOrders`, `getUserMonthAmount`, `getRechargeMonth` |
| City fares | `getFeeRuleByCityId` |
| City lookup | `getCityFences` (`citys` names/IDs, authenticated) |
| Python client automatic-pass status | `getUserAutoBuy` (read only; no CLI or MCP command) |

Ride history fetches current and archived year partitions starting from the
requested start date's year through the current year at most, deduplicates by
`useId`, and filters locally by date. Pass/recharge history
uses the app's successful-history filters (`reStatus=4`, `getType=1`);
RidePass purchases have `reType=7`.

`cities [QUERY]` / MCP `list_cities(query)` returns the current `citys` list
as `cityId` / `cityName` pairs. It sends neutral coordinates (`0,0`) and no
selected city, omits boundary polygons, deduplicates IDs, and optionally filters
names case-insensitively. Use those IDs for city-specific requests. Availability
of the full city list with neutral coordinates still needs live validation with
an authenticated session; the unauthenticated endpoint returns status 401.

The CLI and MCP server expose no ride-control, payment, purchase, cancellation,
or account-editing operations. The Python client's low-level `post()` method
accepts arbitrary endpoint paths; callers using it directly are responsible
for the endpoints they choose.
