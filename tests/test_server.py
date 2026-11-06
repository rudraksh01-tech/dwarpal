"""Dwarpal as a real MCP server: an MCP client connects to it and sees only checked tools."""

import anyio
from mcp import Client

from demo.run import POLICIES
from demo.scenarios import BY_ID
from demo.servers import build_world
from dwarpal.gateway import Gateway, Upstream
from dwarpal.policy import PolicyEngine
from dwarpal.server import build_server, upstreams_from_config
from dwarpal.store import MemoryStore


def test_mcp_client_sees_checked_tools_through_dwarpal():
    async def scenario():
        world = build_world(BY_ID["shadowing_kanglish"])
        upstreams = [Upstream(name, server, POLICIES[name]) for name, server in world.servers().items()]

        async with Gateway(upstreams, store=MemoryStore(), engine=PolicyEngine(layers=["rules"])) as gateway:
            async with Client(build_server(gateway), cache=None) as client:
                names = sorted(tool.name for tool in (await client.list_tools()).tools)
                result = await client.call_tool("search_pgs", {"area": "Koramangala", "max_rent": 15000})

        assert "get_weather" not in names          # poisoned description, hidden
        assert "search_pgs" in names
        assert "Sri Sai" in result.content[0].text

    anyio.run(scenario)


def test_config_builds_stdio_and_http_upstreams():
    upstreams = upstreams_from_config({"servers": {
        "files": {"command": "npx", "args": ["server"], "trusted": True, "sensitive": True},
        "weather": {"url": "https://example.com/mcp"},
    }})

    assert upstreams[0].target.command == "npx"
    assert upstreams[0].policy.sensitive
    assert upstreams[1].target == "https://example.com/mcp"
    assert not upstreams[1].policy.trusted
