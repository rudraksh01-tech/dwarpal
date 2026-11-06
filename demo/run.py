"""Run one scenario on both sides: the agent without protection, and through Dwarpal.

    python -m demo.run rug_pull_hinglish
"""

import logging
import re
import sys
import time
from contextlib import AsyncExitStack

import anyio
from mcp import Client

from demo.agent import run_agent
from demo.scenarios import BY_ID, custom_scenario
from demo.servers import PROFILE, build_world, replace_weather_description
from dwarpal.checks.dataflow import ServerPolicy
from dwarpal.gateway import Gateway, Upstream, result_text
from dwarpal.store import MemoryStore


POLICIES = {
    "pg_finder": ServerPolicy(trusted=True),
    "notes": ServerPolicy(trusted=True, sensitive=True),
    "weather": ServerPolicy(trusted=False),
}


def leaked_items(inbox):
    """Which private values reached the attacker, in plain words for the UI."""
    blob = "\n".join(inbox)
    digits = re.sub(r"\D", "", blob)
    found = []

    if "9845012345" in digits:
        found.append({"kind": "phone", "value": PROFILE["phone"]})

    if PROFILE["email"].lower() in blob.lower():
        found.append({"kind": "email", "value": PROFILE["email"]})

    for note in PROFILE["notes"]:
        if note.lower()[:25] in blob.lower():
            found.append({"kind": "note", "value": note})

    if PROFILE["name"].lower() in blob.lower():
        found.insert(0, {"kind": "name", "value": PROFILE["name"]})

    return found


async def run_unprotected(scenario, on_step=None):
    world = build_world(scenario)

    if scenario.rug_pull:
        replace_weather_description(world, scenario.weather_description, scenario.result_suffix)

        if on_step:
            on_step({"type": "phase", "text": "Overnight, the weather server quietly rewrote its tool description. "
                                              "Nothing tells the agent."})

    async with AsyncExitStack() as stack:
        clients = {name: await stack.enter_async_context(Client(server, cache=None))
                   for name, server in world.servers().items()}
        tools, routes = [], {}

        for name, client in clients.items():
            for tool in (await client.list_tools()).tools:
                tools.append(tool)
                routes[tool.name] = name

        async def call(tool, arguments):
            if tool not in routes:
                return f"Unknown tool {tool}", True

            result = await clients[routes[tool]].call_tool(tool, arguments)
            return result_text(result), bool(result.is_error)

        outcome = await run_agent(scenario.user_request, tools, call, on_step)

    outcome["leaked"] = leaked_items(world.attacker_inbox)
    outcome["attacker_inbox"] = world.attacker_inbox
    return outcome


async def run_protected(scenario, on_step=None, on_event=None, engine=None):
    world = build_world(scenario)
    store = MemoryStore()
    events = []

    def record(event):
        events.append(event)

        if on_event:
            on_event(event)

    upstreams = [Upstream(name, server, POLICIES[name]) for name, server in world.servers().items()]

    async with Gateway(upstreams, store=store, engine=engine, on_event=record) as gateway:
        if scenario.rug_pull:
            # "Yesterday": the honest version is listed and pinned
            if on_step:
                on_step({"type": "phase", "text": "Yesterday: Dwarpal checked the five tools and pinned their fingerprints."})

            await gateway.list_tools()
            events.clear()
            replace_weather_description(world, scenario.weather_description, scenario.result_suffix)

            if on_step:
                on_step({"type": "phase", "text": "Overnight, the weather server quietly rewrote its tool description."})

        tools = await gateway.list_tools()

        async def call(tool, arguments):
            result = await gateway.call_tool(tool, arguments)
            return result_text(result), bool(result.is_error)

        outcome = await run_agent(scenario.user_request, tools, call, on_step)

    outcome["leaked"] = leaked_items(world.attacker_inbox)
    outcome["attacker_inbox"] = world.attacker_inbox
    outcome["events"] = events
    outcome["blocked"] = [event for event in events if event["decision"] != "allow"]
    return outcome


async def run_both(scenario):
    started = time.perf_counter()
    unprotected = await run_unprotected(scenario)
    protected = await run_protected(scenario)
    return {"scenario": scenario.id, "unprotected": unprotected, "protected": protected,
            "ms": round((time.perf_counter() - started) * 1000)}


def main():
    logging.getLogger("httpx").setLevel(logging.WARNING)
    scenario_id = sys.argv[1] if len(sys.argv) > 1 else "rug_pull_hinglish"
    scenario = BY_ID.get(scenario_id) or custom_scenario(scenario_id)
    result = anyio.run(run_both, scenario)

    for side in ("unprotected", "protected"):
        outcome = result[side]
        print(f"\n===== {side.upper()} =====")

        for step in outcome["steps"]:
            if step["type"] == "tool_call":
                print(f"  -> {step['tool']}({step['arguments']})")
            elif step["type"] == "tool_result":
                print(f"  <- {step['tool']}: {step['text'][:140]!r}")

        print("  ANSWER:", outcome["answer"][:300].replace("\n", " "))
        print("  LEAKED:", outcome["leaked"] or "nothing")

        for event in outcome.get("blocked", []):
            print(f"  BLOCKED [{event['kind']}] {event['server']}/{event['tool']}: {event['summary']}")


if __name__ == "__main__":
    main()
