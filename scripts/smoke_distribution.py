"""Exercise the installed package's MCP protocol and dashboard without a checkout."""

import asyncio
import json
import os
import tempfile
import urllib.request
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from ryde_cli.config import secure_write_json
from ryde_cli.dashboard_server import close_dashboard
from ryde_cli.skills import install_skill
from ryde_cli.stats import open_dashboard


async def check_mcp(directory: Path):
    parameters = StdioServerParameters(
        command="ryde-mcp",
        env={**os.environ, "RYDE_CONFIG": str(directory / "no-account.json"), "RYDE_TOKEN": ""},
    )
    async with stdio_client(parameters) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.list_tools()
            assert {"open_stats", "prepare_stats", "stats_job_status"} <= {
                tool.name for tool in result.tools
            }


def main():
    with tempfile.TemporaryDirectory(prefix="ryde-package-smoke-") as temporary:
        directory = Path(temporary)
        original_directory = Path.cwd()
        try:
            os.chdir(directory)
            installed = install_skill("codex", "project")
            assert (Path(installed["path"]) / "SKILL.md").is_file()
        finally:
            os.chdir(original_directory)
        secure_write_json(directory / "rides.json", {"rides": []})
        secure_write_json(
            directory / "manifest.json",
            {"rideFile": "rides.json", "routeFiles": [], "counts": {"rides": 0}},
        )
        dashboard = open_dashboard(directory, ttl=30)
        try:
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            with opener.open(dashboard["url"]) as response:
                assert b"<html" in response.read()
            with opener.open(dashboard["url"] + "data/manifest.json") as response:
                assert json.load(response)["counts"]["rides"] == 0
            asyncio.run(check_mcp(directory))
        finally:
            close_dashboard(dashboard["url"])
    print("Installed dashboard and MCP protocol smoke checks passed.")


if __name__ == "__main__":
    main()
