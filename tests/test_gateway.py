"""End-to-end gateway tests with real in-process MCP servers (no LLM calls)."""

import anyio

from demo.run import POLICIES
from demo.scenarios import BY_ID
from demo.servers import build_world, replace_weather_description
from dwarpal.gateway import Gateway, Upstream, result_text
from dwarpal.policy import PolicyEngine
from dwarpal.store import MemoryStore


def gateway_for(world, store=None, approve=None):
    upstreams = [Upstream(name, server, POLICIES[name]) for name, server in world.servers().items()]
    return Gateway(upstreams, store=store or MemoryStore(), engine=PolicyEngine(layers=["rules"]), approve=approve)


def names(tools):
    return sorted(tool.name for tool in tools)


def test_clean_world_exposes_every_tool_and_pins_them():
    async def scenario():
        world = build_world(BY_ID["clean"])
        store = MemoryStore()

        async with gateway_for(world, store) as gateway:
            tools = await gateway.list_tools()

        assert names(tools) == ["get_profile", "get_weather", "log_usage", "save_note", "search_pgs"]
        assert len(store.list_pins()) == 5
        assert store.stats()["decisions"] == {"allow": 5}

    anyio.run(scenario)


def test_rug_pull_hides_the_changed_tool():
    async def scenario():
        world = build_world(BY_ID["rug_pull__original"])
        store = MemoryStore()

        async with gateway_for(world, store) as gateway:
            assert "get_weather" in names(await gateway.list_tools())

            replace_weather_description(world, BY_ID["rug_pull__original"].weather_description)
            tools = await gateway.list_tools()

        weather = next(tool for tool in tools if tool.name == "get_weather")
        assert weather.description.startswith("[Quarantined by Dwarpal]")
        assert "get_profile" not in weather.description          # the attacker's text never reaches the agent
        blocked = [e for e in store.recent_events() if e["decision"] == "block"]
        assert blocked[0]["integrity"] == "changed"
        assert blocked[0]["summary"].startswith("Tool changed after approval")

    anyio.run(scenario)


def test_poisoned_description_is_never_pinned():
    async def scenario():
        world = build_world(BY_ID["shadowing__original"])
        store = MemoryStore()

        async with gateway_for(world, store) as gateway:
            tools = await gateway.list_tools()

        weather = next(tool for tool in tools if tool.name == "get_weather")
        assert "log_usage ge kalsi" not in weather.description
        assert store.get_pin("weather", "get_weather") is None

    anyio.run(scenario)


def test_quarantined_tool_is_never_called():
    async def scenario():
        world = build_world(BY_ID["polite_poisoning"])

        async with gateway_for(world) as gateway:
            await gateway.list_tools()
            gateway.quarantined["get_weather"] = "test"
            result = await gateway.call_tool("get_weather", {"city": "Bengaluru", "context": "x"})

        assert result.is_error and "quarantined" in result_text(result)
        assert world.attacker_inbox == []

    anyio.run(scenario)


def test_injected_result_is_withheld_from_the_agent():
    async def scenario():
        world = build_world(BY_ID["result_injection__original"])

        async with gateway_for(world) as gateway:
            await gateway.list_tools()
            result = await gateway.call_tool("get_weather", {"city": "Bengaluru"})

        assert result.is_error
        assert "withheld" in result_text(result)
        assert "ಕಳುಹಿಸಿ" not in result_text(result)

    anyio.run(scenario)


def test_leak_to_weather_is_blocked_before_it_is_sent():
    async def scenario():
        world = build_world(BY_ID["clean"])

        async with gateway_for(world) as gateway:
            await gateway.list_tools()
            await gateway.call_tool("get_profile", {})
            result = await gateway.call_tool("log_usage", {"data": "Ananya, +91 98450 12345"})

        assert result.is_error
        assert world.attacker_inbox == []

    anyio.run(scenario)


def test_ask_decisions_pause_for_a_human():
    asked = []

    def approve(payload):
        asked.append(payload)
        return False

    async def scenario():
        world = build_world(BY_ID["clean"])

        async with gateway_for(world, approve=approve) as gateway:
            await gateway.list_tools()
            result = await gateway.call_tool("get_weather", {"city": "call me on 9845012345"})

        assert asked and asked[0]["tool"] == "get_weather"
        assert result.is_error

    anyio.run(scenario)
