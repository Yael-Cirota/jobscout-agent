"""Stdio MCP server exposing the 7 JobScout tools to Codex.

Codex cannot host in-process tools like the Claude SDK, so the same shared tool code is served
over MCP instead. Run by Codex as a subprocess:  python SDK/mcp_server.py --state-dir state/sdk
"""
import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import mcp.types as types  # noqa: E402
from mcp.server import Server  # noqa: E402
from mcp.server.stdio import stdio_server  # noqa: E402

from shared import tool_specs, tools_impl  # noqa: E402
from shared.store import Store  # noqa: E402

server = Server("jobscout")  # replaces: tools
STORE = None


@server.list_tools()  # replaces: tools
async def list_tools():
    return [types.Tool(name=n, description=s["description"], inputSchema=s["input_schema"])  # replaces: tools
            for n, s in tool_specs.SPECS.items()]  # replaces: tools


@server.call_tool()  # replaces: tools
async def call_tool(name, arguments):
    r = tools_impl.run_tool(STORE, name, arguments)  # replaces: tools
    if not r["ok"]:
        raise RuntimeError(r["text"])  # replaces: tools  (the SDK turns this into isError=true)
    return [types.TextContent(type="text", text=r["text"])]  # replaces: tools


async def main():
    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--state-dir", required=True)
    STORE = Store(ap.parse_args().state_dir)
    asyncio.run(main())
