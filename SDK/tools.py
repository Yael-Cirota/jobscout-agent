"""Codex configuration for the JobScout tools (the MCP server entry + restrictions)."""
import json
import os
import sys
from pathlib import Path

from shared import tool_specs

SERVER_SCRIPT = Path(__file__).resolve().parent / "mcp_server.py"
TOOL_NAMES = list(tool_specs.SPECS)  # replaces: tools


def _toml(v):
    """Minimal TOML value encoder (strings, lists, inline tables) for --config overrides."""
    if isinstance(v, dict):
        return "{" + ", ".join(f"{k} = {_toml(x)}" for k, x in v.items()) + "}"
    return json.dumps(v)  # JSON strings/arrays are valid TOML


def config_overrides(state_dir, http_mode, effort):
    """Only the jobscout MCP server and only its 7 tools; no other MCP servers or tools."""
    s = "mcp_servers.jobscout"
    env = {"JOBSCOUT_HTTP": http_mode, "SystemRoot": os.environ.get("SystemRoot", "")}
    return (
        f"{s}.command={_toml(sys.executable)}",  # replaces: tools
        f"{s}.args={_toml([str(SERVER_SCRIPT), '--state-dir', str(Path(state_dir).resolve())])}",  # replaces: tools
        f"{s}.env={_toml(env)}",  # replaces: tools
        f"{s}.enabled_tools={_toml(TOOL_NAMES)}",  # replaces: tools  (restricted tool list)
        f"{s}.default_tools_approval_mode=\"approve\"",  # replaces: tools  (pre-approve only these 7 tools)
        f"model_reasoning_effort={_toml(effort)}",  # same effort as the API version
    )
