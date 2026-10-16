"""Stdio MCP server exposing only a Ryde account owner's read-only data."""

from __future__ import annotations

import datetime as dt
import json
import logging
import sys
from typing import Any

from .analysis import recommend_passes, summarize_rides
from .client import RydeClient, RydeError
from .config import ConfigStore

# Never write protocol messages to stdout. The MCP SDK owns stdout; diagnostics
# use stderr only. A client can configure token/base URL via environment/config.
logging.basicConfig(stream=sys.stderr, level=logging.WARNING)


def _client() -> RydeClient:
    config = ConfigStore()
    return RydeClient(
        token=config.token(), base_url=config.base_url(), mobile_type=config.mobile_type()
    )


def _date(value: str | None) -> dt.date | None:
    return dt.date.fromisoformat(value) if value else None


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2)


def create_server() -> Any:
    """Build a typed stdio server with no mutation-capable tools."""
    # MCP SDK 1.x exposes FastMCP; the newer SDK documentation names the
    # equivalent class MCPServer. Support either public SDK shape so the
    # packaged current version stays usable while future v2 upgrades work.
    try:
        from mcp.server import MCPServer
    except ImportError:
        from mcp.server import FastMCP as MCPServer

    from mcp.types import ToolAnnotations

    mcp = MCPServer("ryde-readonly")
    read_only = ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True)

    @mcp.tool(annotations=read_only)
    def account_profile() -> dict[str, Any]:
        """Return the signed-in owner's profile/account record. Read-only."""
        return _client().profile()

    @mcp.tool(annotations=read_only)
    def current_ride() -> dict[str, Any]:
        """Return current ride status only; this never starts, ends, or alters a ride."""
        return _client().active_ride()

    @mcp.tool(annotations=read_only)
    def list_rides(start: str | None = None, end: str | None = None) -> list[dict[str, Any]]:
        """List completed rides. Dates are inclusive YYYY-MM-DD; omit for all available history."""
        return _client().rides(_date(start), _date(end))

    @mcp.tool(annotations=read_only)
    def ride_detail(use_id: str) -> dict[str, Any]:
        """Fetch detail for one completed ride ID. Read-only."""
        return _client().ride_detail(use_id)

    @mcp.tool(annotations=read_only)
    def ride_order(order_id: str) -> dict[str, Any]:
        """Fetch linked order/charge detail for a completed ride. Read-only."""
        return _client().ride_order(order_id)

    @mcp.tool(annotations=read_only)
    def ride_route(use_id: str, include_sensitive_location: bool = False) -> dict[str, Any]:
        """Fetch stored route GPS only after explicit sensitive-location acknowledgement."""
        if not include_sensitive_location:
            raise RydeError(
                "set include_sensitive_location=true to retrieve sensitive GPS route data"
            )
        return _client().route(use_id)

    @mcp.tool(annotations=read_only)
    def pass_catalogue(city_id: int) -> dict[str, Any]:
        """Return current RidePass products, prices, allowances and validity for a city."""
        return _client().pass_catalogue(city_id)

    @mcp.tool(annotations=read_only)
    def owned_passes() -> dict[str, Any]:
        """Return active/current passes owned by the signed-in account."""
        return _client().owned_passes()

    @mcp.tool(annotations=read_only)
    def recharge_history(all_pages: bool = False, page: int = 0) -> Any:
        """Return pass/recharge purchase history. all_pages may make multiple read-only requests."""
        client = _client()
        if all_pages:
            return client.fetch_pages("recharge", ("recharges", "rechargeOrders", "orders", "data"))
        return client.recharge_history(page)

    @mcp.tool(annotations=read_only)
    def recharge_detail(recharge_id: str) -> dict[str, Any]:
        """Return one recharge/pass receipt by its recharge ID. Read-only."""
        return _client().recharge_detail(recharge_id)

    @mcp.tool(annotations=read_only)
    def vipps_payment_history(all_pages: bool = False, page: int = 0) -> Any:
        """Return read-only Vipps payment-order history for the signed-in account."""
        client = _client()
        if all_pages:
            return client.fetch_pages(
                "vipps", ("userVippsOrders", "orders", "vippsOrders", "paymentOrders", "data")
            )
        return client.vipps_payments(page)

    @mcp.tool(annotations=read_only)
    def account_month_amount(month: str) -> dict[str, Any]:
        """Return account amount data for YYYY-MM. Read-only."""
        return _client().month_amount(month)

    @mcp.tool(annotations=read_only)
    def recharge_month(month: str) -> dict[str, Any]:
        """Return recharge data for YYYY-MM. Read-only."""
        return _client().recharge_month(month)

    @mcp.tool(annotations=read_only)
    def city_fee_rule(city_id: int) -> dict[str, Any]:
        """Return fee/fare rules for a city. Read-only."""
        return _client().fee_rule(city_id)

    @mcp.tool(annotations=read_only)
    def ride_summary(start: str | None = None, end: str | None = None) -> dict[str, Any]:
        """Compute local ride totals, distance, duration, discounts, monthly trend and averages."""
        return summarize_rides(_client().rides(_date(start), _date(end)))

    @mcp.tool(annotations=read_only)
    def recommend_ridepass(
        city_id: int, start: str | None = None, end: str | None = None
    ) -> dict[str, Any]:
        """Compare current city RidePasses against observed rides with stated conservative assumptions."""
        client = _client()
        return recommend_passes(
            client.rides(_date(start), _date(end)),
            client.pass_catalogue(city_id),
            client.fee_rule(city_id),
        )

    @mcp.tool(
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

    @mcp.tool(annotations=read_only)
    def stats_job_status(job_id: str) -> dict[str, Any]:
        """Poll a background stats job. completed results contain counts and, for open_stats, a local dashboard URL."""
        from .stats import dataset_path
        from .stats_job import job_status

        config = ConfigStore()
        return job_status(dataset_path(config, config.token()), job_id)

    @mcp.tool(
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

    @mcp.tool(
        annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=False)
    )
    def close_stats(url: str) -> dict[str, bool]:
        """Stop a local dashboard using its exact returned URL; never sends account credentials."""
        from .dashboard_server import close_dashboard

        return close_dashboard(url)

    @mcp.resource("ryde://account/summary")
    def account_summary_resource() -> str:
        """JSON ride summary for all available history of the configured account."""
        return _json(summarize_rides(_client().rides()))

    @mcp.resource("ryde://city/{city_id}/passes")
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
