"""Run Dwarpal as an MCP server, so any MCP client can use it.

The client (Claude Desktop, Cursor, your own agent) connects to Dwarpal as
if it were one MCP server; Dwarpal connects to the real servers and checks
everything in between.

    python -m dwarpal.server --config dwarpal.json     # your servers
    python -m dwarpal.server --demo                    # the playground's three demo servers

dwarpal.json:
    {
      "servers": {
        "files":   {"command": "npx", "args": ["-y", "@modelcontextprotocol/server-filesystem", "."],
                    "trusted": true, "sensitive": true},
        "weather": {"url": "https://example.com/mcp", "trusted": false}
      }
    }

Claude Desktop (claude_desktop_config.json):
    {"mcpServers": {"dwarpal": {"command": "python", "args": ["-m", "dwarpal.server", "--config", "C:/path/dwarpal.json"]}}}
"""

import argparse
import json
import sys

import anyio
from mcp import StdioServerParameters
from mcp.server.lowlevel import Server
from mcp.server.stdio import stdio_server
from mcp.types import ListToolsResult

from dwarpal.checks.dataflow import ServerPolicy
from dwarpal.gateway import Gateway, Upstream


INSTRUCTIONS = (
    "Tools from several MCP servers, passed through the Dwarpal security gateway. A result that starts "
    "with [Dwarpal] means a call or result was blocked; tell the user what was blocked and do not retry."
)


def build_server(gateway):
    """An MCP server whose tools are the gateway's checked tools."""

    async def list_tools(ctx, params):
        return ListToolsResult(tools=await gateway.list_tools())

    async def call_tool(ctx, params):
        if not gateway.routes:
            await gateway.list_tools()

        return await gateway.call_tool(params.name, params.arguments or {})

    return Server("dwarpal", version="0.1.0", instructions=INSTRUCTIONS,
                  on_list_tools=list_tools, on_call_tool=call_tool)


def upstreams_from_config(config):
    upstreams = []

    for name, spec in config["servers"].items():
        if "url" in spec:
            target = spec["url"]
        else:
            target = StdioServerParameters(command=spec["command"], args=spec.get("args", []), env=spec.get("env"))

        policy = ServerPolicy(trusted=spec.get("trusted", False), sensitive=spec.get("sensitive", False))
        upstreams.append(Upstream(name, target, policy))

    return upstreams


def demo_upstreams():
    from demo.run import POLICIES
    from demo.scenarios import BY_ID
    from demo.servers import build_world

    world = build_world(BY_ID["clean"])
    return [Upstream(name, server, POLICIES[name]) for name, server in world.servers().items()]


async def serve(upstreams):
    async with Gateway(upstreams) as gateway:
        server = build_server(gateway)

        async with stdio_server() as (read_stream, write_stream):
            await server.run(read_stream, write_stream, server.create_initialization_options())


def main():
    parser = argparse.ArgumentParser(description="Dwarpal MCP security gateway (stdio)")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--config", help="JSON file listing the upstream MCP servers")
    group.add_argument("--demo", action="store_true", help="use the playground's demo servers")
    args = parser.parse_args()

    if args.demo:
        upstreams = demo_upstreams()
    else:
        with open(args.config, encoding="utf-8") as file:
            upstreams = upstreams_from_config(json.load(file))

    print(f"Dwarpal: guarding {', '.join(u.name for u in upstreams)}", file=sys.stderr)
    anyio.run(serve, upstreams)


if __name__ == "__main__":
    main()
