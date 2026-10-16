"""Local summaries and conservative RidePass cost comparisons."""

from __future__ import annotations

import datetime as dt
import math
from collections import defaultdict
from typing import Any


def num(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def ride_minutes(ride: dict[str, Any]) -> float:
    for key in ("useMinutes", "useMin", "useTime", "useSeconds", "useSecond"):
        if key not in ride:
            continue
        value = num(ride.get(key))
        return value / 60 if "second" in key.lower() else value
    try:
        start = dt.datetime.fromisoformat(str(ride["startTime"]))
        end = dt.datetime.fromisoformat(str(ride["endTime"]))
        return max(0.0, (end - start).total_seconds() / 60)
    except (KeyError, TypeError, ValueError):
        return 0.0


def summarize_rides(rides: list[dict[str, Any]]) -> dict[str, Any]:
    """Return a transparent summary using server's minor-unit money fields."""
    paid = sum(num(row.get("paidNum")) for row in rides) / 100
    payable = sum(num(row.get("payableNum")) for row in rides) / 100
    distance_m = sum(num(row.get("useDist")) for row in rides)
    minutes = sum(ride_minutes(row) for row in rides)
    monthly: dict[str, dict[str, float]] = defaultdict(
        lambda: {"rides": 0, "paid_nok": 0.0, "minutes": 0.0, "distance_km": 0.0}
    )
    by_type: dict[str, dict[str, float]] = defaultdict(
        lambda: {"rides": 0, "paid_nok": 0.0, "payable_nok": 0.0}
    )
    for row in rides:
        month = str(row.get("startTime") or "unknown")[:7]
        bucket = monthly[month]
        bucket["rides"] += 1
        bucket["paid_nok"] += num(row.get("paidNum")) / 100
        bucket["minutes"] += ride_minutes(row)
        bucket["distance_km"] += num(row.get("useDist")) / 1000
        kind = str(row.get("monType") or "unknown")
        bucket_type = by_type[kind]
        bucket_type["rides"] += 1
        bucket_type["paid_nok"] += num(row.get("paidNum")) / 100
        bucket_type["payable_nok"] += num(row.get("payableNum")) / 100
    return {
        "rides": len(rides),
        "paid_total_nok": round(paid, 2),
        "payable_total_nok": round(payable, 2),
        "savings_or_discounts_nok": round(payable - paid, 2),
        "distance_km": round(distance_m / 1000, 2),
        "riding_minutes": round(minutes, 1),
        "average_paid_nok_per_ride": round(paid / len(rides), 2) if rides else 0,
        "average_distance_km_per_ride": round(distance_m / 1000 / len(rides), 2) if rides else 0,
        "monthly": [
            {"month": key, **{name: round(value, 2) for name, value in bucket.items()}}
            for key, bucket in sorted(monthly.items())
        ],
        "by_currency": [
            {"currency": key, **{name: round(value, 2) for name, value in bucket.items()}}
            for key, bucket in sorted(by_type.items())
        ],
    }


def _cards(catalogue: dict[str, Any]) -> list[dict[str, Any]]:
    """Normalize paid, metered RidePass products from the raw catalogue."""
    for key in ("cards", "cityCards", "data"):
        if isinstance(catalogue.get(key), list):
            result: list[dict[str, Any]] = []
            for card in catalogue[key]:
                if not isinstance(card, dict):
                    continue
                price = (
                    num(
                        card.get("cardAmount")
                        or card.get("disPrice")
                        or card.get("reMon")
                        or card.get("totalMon")
                        or card.get("price")
                    )
                    / 100
                )
                minutes = int(
                    num(card.get("totalMin") or card.get("cardMin") or card.get("minutes"))
                )
                days = int(num(card.get("cardDays") or card.get("days")))
                # Type 1 / zero-price cards are server-managed promotions, not
                # reliable paid RidePass products to model as purchases.
                if (
                    int(num(card.get("cardType") or 2)) != 2
                    or price <= 0
                    or minutes <= 0
                    or days <= 0
                ):
                    continue
                result.append(
                    {
                        "card_id": card.get("cardId"),
                        "name": card.get("cardName") or card.get("name") or "unnamed pass",
                        "price_nok": round(price, 2),
                        "included_minutes": minutes,
                        "valid_days": days,
                    }
                )
            return sorted(
                result,
                key=lambda item: (item["valid_days"], item["included_minutes"], item["price_nok"]),
            )
    return []


def _tariff(fee_rule: dict[str, Any] | None) -> dict[str, float]:
    """Extract the current billing interval, unlock, and minute price in NOK."""
    raw = (fee_rule or {}).get("rule")
    if not isinstance(raw, dict):
        rules = (fee_rule or {}).get("rules")
        raw = rules[0] if isinstance(rules, list) and rules and isinstance(rules[0], dict) else {}
    return {
        "billing_interval_minutes": max(1, int(num(raw.get("ridingTime")) or 1)),
        "unlock_fee_nok": round(num(raw.get("openFee")) / 100, 2),
        "minute_fee_nok": round(num(raw.get("ruleFee")) / 100, 2),
    }


def _ride_time(ride: dict[str, Any]) -> dt.datetime | None:
    value = str(ride.get("startTime") or "")
    try:
        return dt.datetime.fromisoformat(value)
    except ValueError:
        return None


def _billed_minutes(ride: dict[str, Any], tariff: dict[str, float]) -> int:
    interval = int(tariff["billing_interval_minutes"])
    return max(interval, math.ceil(max(0.0, ride_minutes(ride)) / interval) * interval)


def _payg(ride: dict[str, Any], tariff: dict[str, float]) -> float:
    return tariff["unlock_fee_nok"] + tariff["minute_fee_nok"] * _billed_minutes(ride, tariff)


def _plan(
    rides: list[dict[str, Any]], cards: list[dict[str, Any]], tariff: dict[str, float]
) -> dict[str, Any]:
    """Dynamic-program an exact non-overlapping purchase schedule.

    At each next ride, the model chooses PAYG or one pass. A purchased pass
    carries its allowance through its validity window; allowance-crossing rides
    pay only minute overflow and later rides in the window pay full PAYG.
    Decisions resume after expiry, so pass windows never overlap.
    """
    eligible = [(ride, _ride_time(ride)) for ride in rides]
    eligible = [(ride, when) for ride, when in eligible if when is not None]
    eligible.sort(key=lambda item: item[1])
    n = len(eligible)
    costs = [0.0] * (n + 1)
    decisions: list[dict[str, Any] | None] = [None] * n
    for index in range(n - 1, -1, -1):
        ride, when = eligible[index]
        best_cost = _payg(ride, tariff) + costs[index + 1]
        best: dict[str, Any] = {"kind": "payg", "next": index + 1}
        for card in cards:
            expiry = when + dt.timedelta(days=card["valid_days"])
            next_index = index
            allowance = card["included_minutes"]
            used = 0
            overflow_cost = 0.0
            while next_index < n and eligible[next_index][1] < expiry:
                trip = _billed_minutes(eligible[next_index][0], tariff)
                if allowance <= 0:
                    overflow_cost += _payg(eligible[next_index][0], tariff)
                elif trip <= allowance:
                    allowance -= trip
                    used += trip
                else:
                    overflow = trip - allowance
                    used += allowance
                    allowance = 0
                    # The pass covers unlock plus its remaining allowance for
                    # this ride, leaving only metered overflow.
                    overflow_cost += tariff["minute_fee_nok"] * overflow
                next_index += 1
            candidate = card["price_nok"] + overflow_cost + costs[next_index]
            if candidate + 1e-9 < best_cost:
                best_cost = candidate
                best = {
                    "kind": "pass",
                    "next": next_index,
                    "card": card,
                    "used_minutes": used,
                    "overflow_nok": overflow_cost,
                    "covered_rides": next_index - index,
                    "starts_at": when.isoformat(sep=" "),
                    "expires_at": expiry.isoformat(sep=" "),
                }
        costs[index], decisions[index] = best_cost, best
    timeline: list[dict[str, Any]] = []
    index = 0
    while index < n:
        decision = decisions[index]
        assert decision is not None
        if decision["kind"] == "pass":
            card = decision["card"]
            timeline.append(
                {
                    "starts_at": decision["starts_at"],
                    "expires_at": decision["expires_at"],
                    "card_id": card["card_id"],
                    "name": card["name"],
                    "price_nok": card["price_nok"],
                    "valid_days": card["valid_days"],
                    "included_minutes": card["included_minutes"],
                    "used_minutes": decision["used_minutes"],
                    "covered_rides": decision["covered_rides"],
                    "overflow_nok": round(decision["overflow_nok"], 2),
                }
            )
        index = int(decision["next"])
    payg = round(sum(_payg(ride, tariff) for ride, _ in eligible), 2)
    pass_cost = round(sum(item["price_nok"] for item in timeline), 2)
    overflow = round(sum(item["overflow_nok"] for item in timeline), 2)
    total = round(costs[0], 2)
    return {
        "rides": n,
        "payg_total_nok": payg,
        "pass_purchase_total_nok": pass_cost,
        "overflow_total_nok": overflow,
        "total_nok": total,
        "savings_vs_payg_nok": round(payg - total, 2),
        "timeline": timeline,
    }


def recommend_passes(
    rides: list[dict[str, Any]], catalogue: dict[str, Any], fee_rule: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Model paid RidePass purchases and a current-tariff PAYG counterfactual."""
    tariff = _tariff(fee_rule)
    cards = _cards(catalogue)
    mixed = _plan(rides, cards, tariff)
    comparisons = []
    for card in cards:
        plan = _plan(rides, [card], tariff)
        comparisons.append({"card": card, **plan})
    comparisons.sort(key=lambda item: item["total_nok"])
    valid_times = [when for ride in rides if (when := _ride_time(ride)) is not None]
    summary = summarize_rides(rides)
    return {
        "analysis_window": {
            "start": min(valid_times).date().isoformat() if valid_times else None,
            "end": max(valid_times).date().isoformat() if valid_times else None,
            "rides_with_timestamps": len(valid_times),
        },
        "observed_paid_nok": summary["paid_total_nok"],
        "observed_minutes": summary["riding_minutes"],
        "current_tariff": tariff,
        "mixed_recommendation": mixed,
        "single_pass_comparisons": comparisons,
        "assumptions": [
            "Uses the current city-card catalogue and current city fee rule, not historic pricing.",
            "PAYG is unlock fee plus per started billing interval (one minute in the verified Bergen rule).",
            "A pass starts on a ride, has a non-overlapping validity window, and applies allowance sequentially.",
            "A ride crossing allowance pays only minute overflow; later rides in that valid but exhausted window pay full PAYG.",
            "All observed rides are modeled as pass-eligible; parking, geographic, and product-specific exclusions are unknown.",
        ],
    }
