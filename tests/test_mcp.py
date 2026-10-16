import asyncio

import pytest

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
        } <= tools
        assert len(tools) == 20
        assert len(await server.list_resources()) == 1
        assert len(await server.list_resource_templates()) == 1
        with pytest.raises(Exception, match="include_sensitive_location"):
            await server.call_tool("ride_route", {"use_id": "synthetic"})

    asyncio.run(check())
