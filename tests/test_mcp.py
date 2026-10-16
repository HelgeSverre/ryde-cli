import asyncio

import pytest
from mcp.server.mcpserver.exceptions import ResourceError, ToolError

from ryde_cli.mcp_server import create_server


def test_mcp_tools_and_resources_can_initialize_without_account():
    async def check():
        server = create_server()
        tools = {tool.name for tool in await server.list_tools()}
        assert {
            "prepare_stats",
            "open_stats",
            "close_stats",
            "stats_job_status",
            "ride_route",
            "ride_summary",
            "list_cities",
        } <= tools
        assert len(tools) == 21
        assert len(await server.list_resources()) == 1
        assert len(await server.list_resource_templates()) == 1
        with pytest.raises(ToolError, match="include_sensitive_location"):
            await server.call_tool("ride_route", {"use_id": "synthetic"})
        route = next(tool for tool in await server.list_tools() if tool.name == "ride_route")
        assert set(route.input_schema["properties"]) == {"use_id", "include_sensitive_location"}
        with pytest.raises(ToolError, match="log in"):
            await server.call_tool("account_profile", {})
        with pytest.raises(ResourceError, match="log in"):
            await server.read_resource("ryde://account/summary")

    asyncio.run(check())


def test_mcp_city_lookup_passes_query_to_client(monkeypatch):
    class Client:
        def cities(self, query):
            assert query == "sample"
            return [{"cityId": 101, "cityName": "Sample City"}]

    monkeypatch.setattr("ryde_cli.mcp_server._client", Client)

    async def check():
        result = await create_server().call_tool("list_cities", {"query": "sample"})
        assert "Sample City" in str(result)

    asyncio.run(check())


def test_mcp_preserves_expected_config_errors(tmp_path, monkeypatch):
    path = tmp_path / "config.json"
    path.write_bytes(b"\xffsynthetic-private-config")
    path.chmod(0o600)
    monkeypatch.setenv("RYDE_CONFIG", str(path))

    async def check():
        server = create_server()
        with pytest.raises(ToolError, match="could not parse") as result:
            await server.call_tool("account_profile", {})
        assert "synthetic-private-config" not in str(result.value)

    asyncio.run(check())


@pytest.mark.parametrize("tool", ["list_rides", "prepare_stats"])
def test_mcp_invalid_dates_have_readable_errors(monkeypatch, tool):
    monkeypatch.setenv("RYDE_TOKEN", "synthetic-token")

    async def check():
        with pytest.raises(ToolError, match="YYYY-MM-DD"):
            await create_server().call_tool(tool, {"start": "not-a-date"})

    asyncio.run(check())
