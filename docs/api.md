# API compatibility

This is an unofficial client for a private Android API. Compatibility may change.
The default API URL is `https://qw-test.ryde.vip/`; that hostname comes from the
compatible app profile and should not be assumed to be a sandbox.

The request profile uses app version `5.16.1`, `okhttp/4.12.0`, and a Galaxy
S21-style `MobileType`. Login generates an Android-style device ID and saves it
locally. No Android emulator, proxy, or OpenSSL executable is required.

The integrity field for form POSTs is:

```text
timeSign = lowercase_md5(base64(aes_128_cbc_pkcs7(
    "rydeGood:<timestamp_ms>:ryde-app",
    key="a70678d869319dab", iv="0102330405070708")))
```

`sendSms` signs the E.164 phone number using the same AES/Base64 operation.
These constants reproduce the app protocol; they are not account credentials.
Signing is not a substitute for server-side access controls.

| Capability | Endpoint(s) |
| --- | --- |
| Login | `checkUserPhone`, `getPhoneCode`, `sendSms`, `userLogin` |
| Profile / current ride | `getUserInfoByToken`, `getUserUseNow` |
| Rides / orders | `getUserAllUseLog`, `getUserUseLogByUseId`, `getOrderInfoById` |
| Stored GPS route | `getLocusByUseId` |
| Passes / recharge receipts | `getCityCards`, `getUserCards`, `getRechargeList`, `getRechargeById` |
| Payments / monthly amounts | `getUserVippsOrders`, `getUserMonthAmount`, `getRechargeMonth` |
| City fares | `getFeeRuleByCityId` |
| Python client automatic-pass status | `getUserAutoBuy` (read only; no CLI or MCP command) |

Ride history fetches current and archived year partitions from 2024 onward,
deduplicates by `useId`, and filters locally by date. Pass/recharge history
uses the app's successful-history filters (`reStatus=4`, `getType=1`);
RidePass purchases have `reType=7`.

The CLI and MCP server expose no ride-control, payment, purchase, cancellation,
or account-editing operations. The Python client's low-level `post()` method
accepts arbitrary endpoint paths; callers using it directly are responsible
for the endpoints they choose.
