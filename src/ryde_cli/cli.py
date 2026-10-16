"""Command-line interface for personal, read-only Ryde account data."""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import getpass
import json
import os
import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from . import __version__
from .analysis import recommend_passes, summarize_rides
from .client import AuthenticationRequired, RydeClient, RydeError, normalise_phone
from .config import ConfigError, ConfigStore, secure_write_json, secure_write_text


def date_arg(value: str) -> dt.date:
    try:
        return dt.date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("expected YYYY-MM-DD") from exc


def client_from(args: argparse.Namespace, *, token: bool = True) -> tuple[RydeClient, ConfigStore]:
    store = ConfigStore(args.config)
    return RydeClient(
        token=store.token() if token else "",
        base_url=args.base_url or store.base_url(),
        mobile_type=args.mobile_type or store.mobile_type(),
    ), store


def _flat(value: Any, prefix: str = "") -> dict[str, Any]:
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for key, item in value.items():
            result.update(_flat(item, f"{prefix}{key}."))
        return result
    if isinstance(value, list):
        return {prefix[:-1]: json.dumps(value, ensure_ascii=False, separators=(",", ":"))}
    return {prefix[:-1] or "value": value}


def _records(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [_flat(row) if isinstance(row, dict) else {"value": row} for row in value]
    if isinstance(value, dict):
        return [_flat(value)]
    return [{"value": value}]


def render(value: Any, fmt: str, output: str | None = None) -> None:
    """Render JSON, CSV, TSV, or compact human table without leaking config."""
    if fmt == "json":
        content = json.dumps(value, ensure_ascii=False, indent=2) + "\n"
    elif fmt in {"csv", "tsv"}:
        rows = _records(value)
        fields = list(dict.fromkeys(key for row in rows for key in row))
        import io

        buffer = io.StringIO()
        writer = csv.DictWriter(
            buffer,
            fieldnames=fields,
            delimiter="\t" if fmt == "tsv" else ",",
            extrasaction="ignore",
        )
        writer.writeheader()
        writer.writerows(rows)
        content = buffer.getvalue()
    else:
        rows = _records(value)
        columns = list(dict.fromkeys(key for row in rows for key in row))[:8]
        if not rows:
            content = "No records.\n"
        else:
            strings = [[str(row.get(column, ""))[:48] for column in columns] for row in rows]
            widths = [
                max(len(column), *(len(row[index]) for row in strings))
                for index, column in enumerate(columns)
            ]
            line = "  ".join(column.ljust(widths[index]) for index, column in enumerate(columns))
            divider = "  ".join("-" * width for width in widths)
            body = [
                "  ".join(cell.ljust(widths[index]) for index, cell in enumerate(row))
                for row in strings
            ]
            content = "\n".join([line, divider, *body]) + "\n"
    if output:
        path = Path(output).expanduser()
        secure_write_json(path, value) if fmt == "json" else secure_write_text(path, content)
        print(f"Wrote {path} with permissions 0600.", file=sys.stderr)
    else:
        sys.stdout.write(content)


def response_list(response: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract the first top-level list from an API response, if present."""
    for value in response.values():
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    return []


def command_login(args: argparse.Namespace) -> None:
    if not args.phone and not sys.stdin.isatty():
        raise RydeError("non-interactive login requires --phone and --send-sms or --sms-code")
    client, store = client_from(args, token=False)
    raw_phone = args.phone or input("Phone number (local or E.164): ").strip()
    phone, country_code = normalise_phone(raw_phone, args.country_code)
    device = args.device or store.device_id()
    check = client.check_phone(phone, country_code, device)
    options = client.phone_code_options(phone, country_code)
    if str(options.get("isImgCode", "0")) not in {"0", "false", "False"}:
        raise RydeError(
            "Ryde requires an image challenge; finish login in the official app and retry later"
        )
    now = time.time()
    last_request = float(store.data.get("last_sms_at", 0) or 0)
    wait = max(0, int(60 - (now - last_request)))
    if args.sms_code:
        code = args.sms_code
    else:
        send = args.send_sms
        if not send and sys.stdin.isatty():
            answer = input(f"Phone accepted. Send an SMS code to {phone}? [y/N] ").strip().lower()
            send = answer in {"y", "yes"}
        if not send:
            raise RydeError(
                "SMS not sent. Re-run with --send-sms after you are ready to receive it"
            )
        if wait and not args.force:
            raise RydeError(
                f"an SMS was requested {60 - wait}s ago; refusing a duplicate for {wait}s (use --force only if needed)"
            )
        client.request_sms(phone, country_code, device)
        store.data["last_sms_at"] = now
        store.save()
        if not sys.stdin.isatty():
            print("SMS requested. Re-run with --sms-code CODE to complete login.", file=sys.stderr)
            return
        code = getpass.getpass("SMS code: ").strip()
    if not code:
        raise RydeError("an SMS code is required")
    result = client.login(
        phone,
        country_code,
        code,
        device,
        args.phone_info or store.phone_info(),
        args.latitude,
        args.longitude,
    )
    token = result.get("token")
    if not isinstance(token, str) or not token:
        raise RydeError("login succeeded but no account token was returned")
    store.data.update(
        {
            "token": token,
            "base_url": client.base_url,
            "mobile_type": client.mobile_type,
            "phone_info": args.phone_info or store.phone_info(),
            "device_id": device,
            "logged_in_at": dt.datetime.now(dt.UTC).isoformat(),
        }
    )
    store.save()
    # Deliberately do not print token or phone.
    render(
        {
            "logged_in": True,
            "config": str(store.path),
            "token_saved": True,
            "phone_check": check.get("message", "ok"),
        },
        args.format,
    )


def command_account(args: argparse.Namespace) -> None:
    client, _ = client_from(args)
    render(
        client.profile() if args.account_command == "profile" else client.active_ride(),
        args.format,
        args.output,
    )


def command_rides(args: argparse.Namespace) -> None:
    client, _ = client_from(args)
    if args.rides_command == "list":
        render(client.rides(args.start, args.end), args.format, args.output)
    elif args.rides_command == "detail":
        render(client.ride_detail(args.use_id), args.format, args.output)
    elif args.rides_command == "order":
        render(client.ride_order(args.order_id), args.format, args.output)
    else:
        if not args.include_location:
            raise RydeError(
                "route data is sensitive; add --include-location to explicitly fetch it"
            )
        render(client.route(args.use_id), args.format, args.output)


def command_passes(args: argparse.Namespace) -> None:
    client, _ = client_from(args)
    if args.passes_command == "catalogue":
        render(client.pass_catalogue(args.city_id), args.format, args.output)
    elif args.passes_command == "owned":
        render(client.owned_passes(), args.format, args.output)
    else:
        records = (
            client.fetch_pages("recharge", ("recharges", "rechargeOrders", "orders", "data"))
            if args.all
            else response_list(client.recharge_history(args.page))
        )
        render(records, args.format, args.output)


def command_payments(args: argparse.Namespace) -> None:
    client, _ = client_from(args)
    if args.payments_command == "recharge-detail":
        value = client.recharge_detail(args.recharge_id)
    elif args.payments_command == "month-amount":
        value = client.month_amount(args.month)
    elif args.payments_command == "recharge-month":
        value = client.recharge_month(args.month)
    else:
        value = (
            client.fetch_pages(
                "vipps", ("userVippsOrders", "orders", "vippsOrders", "paymentOrders", "data")
            )
            if args.all
            else response_list(client.vipps_payments(args.page))
        )
    render(value, args.format, args.output)


def command_fees(args: argparse.Namespace) -> None:
    client, _ = client_from(args)
    render(client.fee_rule(args.city_id), args.format, args.output)


def command_summary(args: argparse.Namespace) -> None:
    client, _ = client_from(args)
    render(summarize_rides(client.rides(args.start, args.end)), args.format, args.output)


def command_optimize(args: argparse.Namespace) -> None:
    client, _ = client_from(args)
    rides = client.rides(args.start, args.end)
    render(
        recommend_passes(rides, client.pass_catalogue(args.city_id), client.fee_rule(args.city_id)),
        args.format,
        args.output,
    )


def command_export(args: argparse.Namespace) -> None:
    # Calls the same command functions but requires an explicit path/format.
    dispatch: dict[str, Callable[[argparse.Namespace], None]] = {
        "rides": command_rides,
        "profile": command_account,
        "catalogue": command_passes,
        "owned-passes": command_passes,
        "recharges": command_passes,
        "vipps": command_payments,
        "fee-rule": command_fees,
        "summary": command_summary,
        "recommendation": command_optimize,
    }
    resource = args.resource
    args.output = args.output or f"ryde-{resource}.{args.format}"
    if resource == "rides":
        args.rides_command = "list"
    elif resource == "profile":
        args.account_command = "profile"
    elif resource in {"catalogue", "owned-passes", "recharges"}:
        args.passes_command = {
            "catalogue": "catalogue",
            "owned-passes": "owned",
            "recharges": "history",
        }[resource]
    elif resource == "vipps":
        args.payments_command = "vipps"
    dispatch[resource](args)


def command_stats(args: argparse.Namespace) -> None:
    from .dashboard_server import close_dashboard
    from .stats import dataset_path, open_dashboard, prepare_stats

    if args.stop:
        render(close_dashboard(args.stop), args.format, args.output)
        return
    if not 0 <= args.port <= 65535 or not 1 <= args.ttl <= 86400:
        raise RydeError("port must be 0–65535 and ttl must be 1–86400 seconds")
    client, store = client_from(args)
    directory = dataset_path(store, client.token, args.data_dir)
    if not args.no_fetch:
        print(
            "Fetching stats data. Route traces are cached; interrupted fetches can be resumed.",
            file=sys.stderr,
        )
        result = prepare_stats(
            client,
            directory,
            start=args.start,
            end=args.end,
            include_location=args.include_location,
        )
    else:
        result = {"data_dir": str(directory)}
    if not args.fetch_only:
        result.update(
            open_dashboard(directory, port=args.port, ttl=args.ttl, open_browser=not args.no_open)
        )
    render(result, args.format, args.output)


def command_skill(args: argparse.Namespace) -> None:
    from .skills import install_skill

    render(install_skill(args.agent, args.scope, force=args.force), args.format)


def _common(parser: argparse.ArgumentParser, *, output: bool = True) -> None:
    parser.add_argument(
        "--format",
        choices=("json", "csv", "tsv", "table"),
        default="json",
        help="output format (JSON default)",
    )
    if output:
        parser.add_argument("--output", help="write results owner-only (0600) instead of stdout")


def _range(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--start", type=date_arg, default=dt.date(2018, 1, 1))
    parser.add_argument("--end", type=date_arg, default=dt.date.today())


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ryde", description=__doc__)
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument(
        "--config",
        help="0600 token/config file (default: $RYDE_CONFIG or ~/.config/ryde-cli/config.json)",
    )
    parser.add_argument("--base-url", help="override $RYDE_BASE_URL/config base URL")
    parser.add_argument(
        "--mobile-type", help="override $RYDE_MOBILE_TYPE/config Android descriptor"
    )
    commands = parser.add_subparsers(dest="command", required=True)
    login = commands.add_parser(
        "login", help="guided SMS login; requests at most one SMS per minute"
    )
    login.add_argument("--phone", help="local or E.164 phone number; omitted prompts interactively")
    login.add_argument("--country-code", default=os.environ.get("RYDE_COUNTRY_CODE", "+47"))
    login.add_argument(
        "--device", help="stable Android-style device id; generated/saved when omitted"
    )
    login.add_argument("--phone-info", help="Android phone information string")
    login.add_argument(
        "--latitude", type=float, default=float(os.environ.get("RYDE_LATITUDE", "0"))
    )
    login.add_argument(
        "--longitude", type=float, default=float(os.environ.get("RYDE_LONGITUDE", "0"))
    )
    login.add_argument(
        "--send-sms", action="store_true", help="explicitly send a code in non-interactive use"
    )
    login.add_argument(
        "--force", action="store_true", help="bypass the local 60 second duplicate-SMS guard"
    )
    login.add_argument(
        "--sms-code", help="complete an already requested login without sending another SMS"
    )
    _common(login, output=False)
    login.set_defaults(func=command_login)

    account = commands.add_parser("account", help="account data")
    _common(account)
    account_sub = account.add_subparsers(dest="account_command", required=True)
    account_sub.add_parser("profile", help="account/profile record")
    account_sub.add_parser("active-ride", help="current ride status only; never changes ride state")
    account.set_defaults(func=command_account)

    rides = commands.add_parser("rides", help="ride history, detail, and opt-in route data")
    _common(rides)
    rides_sub = rides.add_subparsers(dest="rides_command", required=True)
    list_p = rides_sub.add_parser("list", help="all completed ride records in date range")
    _range(list_p)
    detail_p = rides_sub.add_parser("detail", help="one completed ride")
    detail_p.add_argument("use_id")
    order_p = rides_sub.add_parser("order", help="linked charge/order detail for a completed ride")
    order_p.add_argument("order_id")
    route_p = rides_sub.add_parser("route", help="sensitive recorded route points")
    route_p.add_argument("use_id")
    route_p.add_argument(
        "--include-location",
        action="store_true",
        help="required acknowledgement for sensitive GPS data",
    )
    rides.set_defaults(func=command_rides)

    passes = commands.add_parser(
        "passes", help="RidePass catalog, owned cards, and purchase/recharge history"
    )
    _common(passes)
    passes_sub = passes.add_subparsers(dest="passes_command", required=True)
    cat = passes_sub.add_parser("catalogue", help="current city RidePass catalogue/prices")
    cat.add_argument("--city-id", required=True, type=int)
    passes_sub.add_parser("owned", help="currently owned/active cards")
    history = passes_sub.add_parser("history", help="recharge/pass purchase history")
    history.add_argument("--page", type=int, default=0)
    history.add_argument("--all", action="store_true", help="page through all available history")
    passes.set_defaults(func=command_passes)

    payments = commands.add_parser("payments", help="read-only payment order/recharge records")
    _common(payments)
    payments_sub = payments.add_subparsers(dest="payments_command", required=True)
    vp = payments_sub.add_parser("vipps", help="Vipps order history")
    vp.add_argument("--page", type=int, default=0)
    vp.add_argument("--all", action="store_true")
    rd = payments_sub.add_parser("recharge-detail", help="one recharge receipt/detail")
    rd.add_argument("recharge_id")
    month_amount = payments_sub.add_parser("month-amount", help="one month of account amount data")
    month_amount.add_argument("month", help="YYYY-MM")
    recharge_month = payments_sub.add_parser("recharge-month", help="one month of recharge data")
    recharge_month.add_argument("month", help="YYYY-MM")
    payments.set_defaults(func=command_payments)

    fees = commands.add_parser("fees", help="city fare/fee rule data")
    _common(fees)
    fees.add_argument("--city-id", required=True, type=int)
    fees.set_defaults(func=command_fees)

    summary = commands.add_parser("summary", help="local summary of fetched ride history")
    _common(summary)
    _range(summary)
    summary.set_defaults(func=command_summary)
    optimize = commands.add_parser(
        "optimize", help="conservative current RidePass comparison against your history"
    )
    _common(optimize)
    _range(optimize)
    optimize.add_argument("--city-id", required=True, type=int)
    optimize.set_defaults(func=command_optimize)

    export = commands.add_parser("export", help="fetch and save one supported read-only resource")
    _common(export)
    export.add_argument(
        "resource",
        choices=(
            "rides",
            "profile",
            "catalogue",
            "owned-passes",
            "recharges",
            "vipps",
            "fee-rule",
            "summary",
            "recommendation",
        ),
    )
    _range(export)
    export.add_argument(
        "--city-id",
        type=int,
        default=15,
        help="needed for catalogue/fee-rule/recommendation (default 15)",
    )
    export.add_argument("--page", type=int, default=0)
    export.add_argument("--all", action="store_true")
    export.set_defaults(func=command_export)

    stats = commands.add_parser(
        "stats", help="fetch your data and open the bundled local map dashboard"
    )
    _common(stats)
    _range(stats)
    stats.add_argument(
        "--include-location",
        action="store_true",
        help="also fetch precise stored GPS traces (otherwise use ride endpoints)",
    )
    stats.add_argument("--data-dir", help="override the private, account-scoped dataset directory")
    mode = stats.add_mutually_exclusive_group()
    mode.add_argument(
        "--fetch-only", action="store_true", help="fetch data without starting a server"
    )
    mode.add_argument(
        "--no-fetch",
        action="store_true",
        help="open an already prepared dataset without API requests",
    )
    stats.add_argument(
        "--no-open", action="store_true", help="return the URL without opening a browser"
    )
    stats.add_argument("--port", type=int, default=0, help="loopback port; 0 selects a free port")
    stats.add_argument(
        "--ttl", type=int, default=3600, help="server lifetime in seconds (1–86400; default 3600)"
    )
    stats.add_argument(
        "--stop", metavar="URL", help="stop a dashboard using its exact returned URL"
    )
    stats.set_defaults(func=command_stats)

    skill = commands.add_parser(
        "skill", help="install the bundled Ryde workflow skill for Codex or Claude"
    )
    _common(skill, output=False)
    skill.add_argument("--agent", choices=("codex", "claude"), required=True)
    skill.add_argument(
        "--scope",
        choices=("project", "user"),
        default="project",
        help="installation scope (default: current project)",
    )
    skill.add_argument("--force", action="store_true", help="replace existing skill files")
    skill.set_defaults(func=command_skill)
    return parser


def normalize_parent_options(argv: list[str]) -> list[str]:
    """Let agent callers place common options before or after subcommands.

    argparse assigns options to the parser currently consuming tokens. Moving
    root and first-level common options preserves its helpful native help while
    accepting natural forms such as ``ryde rides list --format csv``.
    """
    root_flags = {"--config", "--base-url", "--mobile-type"}
    group_flags = {"--format", "--output"}
    root: list[str] = []
    group: list[str] = []
    remaining: list[str] = []
    index = 0
    while index < len(argv):
        item = argv[index]
        if item in root_flags | group_flags:
            if index + 1 >= len(argv):
                remaining.append(item)
                index += 1
                continue
            target = root if item in root_flags else group
            target.extend([item, argv[index + 1]])
            index += 2
        else:
            remaining.append(item)
            index += 1
    if not remaining:
        return root + group
    return root + [remaining[0], *group, *remaining[1:]]


def main(argv: list[str] | None = None) -> None:
    import argcomplete

    parser = build_parser()
    argcomplete.autocomplete(parser)
    args = parser.parse_args(normalize_parent_options(list(sys.argv[1:] if argv is None else argv)))
    try:
        args.func(args)
    except (RydeError, ConfigError, AuthenticationRequired) as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
    except KeyboardInterrupt:
        print("Interrupted.", file=sys.stderr)
        raise SystemExit(130) from None


if __name__ == "__main__":
    main()
