"""Stdio MCP server exposing only a Ryde account owner's read-only data."""

from __future__ import annotations

import datetime as dt
import json
import logging
import sys
from functools import wraps
from typing import Any

from .analysis import recommend_passes, summarize_rides
from .client import RydeClient, RydeError
from .config import ConfigError, ConfigStore

# Never write protocol messages to stdout. The MCP SDK owns stdout; diagnostics
# use stderr only. A client can configure token/base URL via environment/config.
logging.basicConfig(stream=sys.stderr, level=logging.WARNING)


def _client() -> RydeClient:
    config = ConfigStore()
    return RydeClient(
        token=config.token(), base_url=config.base_url(), mobile_type=config.mobile_type()
    )


def _date(value: str | None) -> dt.date | None:
    try:
        return dt.date.fromisoformat(value) if value else None
    except ValueError:
        raise RydeError("dates must use YYYY-MM-DD") from None


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2)


def create_server() -> Any:
    """Build a typed stdio server with no mutation-capable tools."""
    from mcp.server import MCPServer
    from mcp.server.mcpserver.exceptions import ResourceError, ToolError
    from mcp.types import ToolAnnotations

    mcp = MCPServer("ryde-readonly")

    # Register wrapped functions through the public API so their schemas stay
    # intact and expected errors remain readable under MCP SDK 2.x.
    def expected_errors(error_type: type[Exception]) -> Any:
        def decorate(function: Any) -> Any:
            @wraps(function)
            def call(*args: Any, **kwargs: Any) -> Any:
                try:
                    return function(*args, **kwargs)
                except (RydeError, ConfigError) as exc:
                    raise error_type(str(exc)) from exc

            return call

        return decorate

    def tool(**options: Any) -> Any:
        def register(function: Any) -> Any:
            return mcp.tool(**options)(expected_errors(ToolError)(function))

        return register

    read_only = ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True)

    @tool(annotations=read_only)
    def list_cities(query: str | None = None) -> list[dict[str, Any]]:
        """Look up available city names and IDs. Optional case-insensitive name filter. Call before city-specific passes, fares or recommendations; never guess IDs."""
        return _client().cities(query)

    @tool(annotations=read_only)
    def account_profile() -> dict[str, Any]:
        """Return the signed-in owner's profile/account record. Read-only."""
        return _client().profile()

    @tool(annotations=read_only)
    def current_ride() -> dict[str, Any]:
        """Return current ride status only; this never starts, ends, or alters a ride."""
        return _client().active_ride()

    @tool(annotations=read_only)
    def list_rides(start: str | None = None, end: str | None = None) -> list[dict[str, Any]]:
        """List completed rides. Dates are inclusive YYYY-MM-DD; omit for all available history."""
        return _client().rides(_date(start), _date(end))

    @tool(annotations=read_only)
    def ride_detail(use_id: str) -> dict[str, Any]:
        """Fetch detail for one completed ride ID. Read-only."""
        return _client().ride_detail(use_id)

    @tool(annotations=read_only)
    def ride_order(order_id: str) -> dict[str, Any]:
        """Fetch linked order/charge detail for a completed ride. Read-only."""
        return _client().ride_order(order_id)

    @tool(annotations=read_only)
    def ride_route(use_id: str, include_sensitive_location: bool = False) -> dict[str, Any]:
        """Fetch stored route GPS only after explicit sensitive-location acknowledgement."""
        if not include_sensitive_location:
            raise RydeError(
                "set include_sensitive_location=true to retrieve sensitive GPS route data"
            )
        return _client().route(use_id)

    @tool(annotations=read_only)
    def pass_catalogue(city_id: int) -> dict[str, Any]:
        """Return current RidePass products and prices. Resolve city_id with list_cities first."""
        return _client().pass_catalogue(city_id)

    @tool(annotations=read_only)
    def owned_passes() -> dict[str, Any]:
        """Return active/current passes owned by the signed-in account."""
        return _client().owned_passes()

    @tool(annotations=read_only)
    def recharge_history(all_pages: bool = False, page: int = 0) -> Any:
        """Return pass/recharge purchase history. all_pages may make multiple read-only requests."""
        client = _client()
        if all_pages:
            return client.fetch_pages("recharge", ("recharges", "rechargeOrders", "orders", "data"))
        return client.recharge_history(page)

    @tool(annotations=read_only)
    def recharge_detail(recharge_id: str) -> dict[str, Any]:
        """Return one recharge/pass receipt by its recharge ID. Read-only."""
        return _client().recharge_detail(recharge_id)

    @tool(annotations=read_only)
    def vipps_payment_history(all_pages: bool = False, page: int = 0) -> Any:
        """Return read-only Vipps payment-order history for the signed-in account."""
        client = _client()
        if all_pages:
            return client.fetch_pages(
                "vipps", ("userVippsOrders", "orders", "vippsOrders", "paymentOrders", "data")
            )
        return client.vipps_payments(page)

    @tool(annotations=read_only)
    def account_month_amount(month: str) -> dict[str, Any]:
        """Return account amount data for YYYY-MM. Read-only."""
        return _client().month_amount(month)

    @tool(annotations=read_only)
    def recharge_month(month: str) -> dict[str, Any]:
        """Return recharge data for YYYY-MM. Read-only."""
        return _client().recharge_month(month)

    @tool(annotations=read_only)
    def city_fee_rule(city_id: int) -> dict[str, Any]:
        """Return fee/fare rules. Resolve city_id with list_cities first. Read-only."""
        return _client().fee_rule(city_id)

    @tool(annotations=read_only)
    def ride_summary(start: str | None = None, end: str | None = None) -> dict[str, Any]:
        """Compute local ride totals, distance, duration, discounts, monthly trend and averages."""
        return summarize_rides(_client().rides(_date(start), _date(end)))

    @tool(annotations=read_only)
    def recommend_ridepass(
        city_id: int, start: str | None = None, end: str | None = None
    ) -> dict[str, Any]:
        """Compare city RidePasses against observed rides with conservative assumptions. Resolve city_id with list_cities first."""
        client = _client()
        return recommend_passes(
            client.rides(_date(start), _date(end)),
            client.pass_catalogue(city_id),
            client.fee_rule(city_id),
        )

    @tool(
        annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=False)
    )
    def prepare_stats(
        include_sensitive_location: bool = False,
        start: str | None = None,
        end: str | None = None,
    ) -> dict[str, Any]:
        """Start a resumable background export; poll stats_job_status with the returned job_id. Route GPS requires explicit consent."""
        from .stats_job import start_job

        config = ConfigStore()
        return start_job(config, include_location=include_sensitive_location, start=start, end=end)

    @tool(annotations=read_only)
    def stats_job_status(job_id: str) -> dict[str, Any]:
        """Poll a background stats job. completed results contain counts and, for open_stats, a local dashboard URL."""
        from .stats import dataset_path
        from .stats_job import job_status

        config = ConfigStore()
        return job_status(dataset_path(config, config.token()), job_id)

    @tool(
        annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=False)
    )
    def open_stats(
        refresh: bool = True,
        include_sensitive_location: bool = False,
        start: str | None = None,
        end: str | None = None,
        open_browser: bool = False,
        ttl: int = 3600,
    ) -> dict[str, Any]:
        """Start a background fetch-and-open job; poll stats_job_status for its URL. refresh=false opens cached data immediately. Browser opens on the MCP host only."""
        from .stats import dataset_path, open_dashboard
        from .stats_job import start_job

        config = ConfigStore()
        if refresh:
            return start_job(
                config,
                include_location=include_sensitive_location,
                start=start,
                end=end,
                open_when_ready=True,
                open_browser=open_browser,
                ttl=ttl,
            )
        client = _client()
        directory = dataset_path(config, client.token)
        return {
            "data_dir": str(directory),
            **open_dashboard(directory, ttl=ttl, open_browser=open_browser),
        }

    @tool(
        annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=False)
    )
    def close_stats(url: str) -> dict[str, bool]:
        """Stop a local dashboard using its exact returned URL; never sends account credentials."""
        from .dashboard_server import close_dashboard

        return close_dashboard(url)

    @mcp.resource("ryde://account/summary")
    @expected_errors(ResourceError)
    def account_summary_resource() -> str:
        """JSON ride summary for all available history of the configured account."""
        return _json(summarize_rides(_client().rides()))

    @mcp.resource("ryde://city/{city_id}/passes")
    @expected_errors(ResourceError)
    def city_pass_resource(city_id: str) -> str:
        """JSON current RidePass catalogue for a city."""
        return _json(_client().pass_catalogue(city_id))

    return mcp


def main() -> None:
    try:
        create_server().run()
    except RydeError as exc:
        print(f"Ryde MCP error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
