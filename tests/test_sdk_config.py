import asyncio
import os
import sys
from pathlib import Path

import pytest

from shared import tool_specs
from SDK import tools as sdk_tools


def test_overrides_only_jobscout_with_all_seven_tools(tmp_path):
    ov = sdk_tools.config_overrides(tmp_path, "replay", "medium")
    assert all(o.startswith(("mcp_servers.jobscout.", "model_reasoning_effort=")) for o in ov)
    enabled = [o for o in ov if ".enabled_tools=" in o][0]
    assert all(f'"{n}"' in enabled for n in tool_specs.SPECS) and len(tool_specs.SPECS) == 7
    assert any('JOBSCOUT_HTTP = "replay"' in o for o in ov)
    assert any("mcp_server.py" in o for o in ov) and 'model_reasoning_effort="medium"' in ov


def test_agent_options_source_has_required_settings():
    src = (Path(__file__).resolve().parent.parent / "SDK" / "agent.py").read_text()
    for needle in ("developer_instructions=prompts.SYSTEM_PROMPT", "Sandbox.read_only",
                   "ApprovalMode.deny_all", "thread_resume(", "thread_start(", "AGENTS.md"):
        assert needle in src, needle


def test_main_ignores_openai_key_and_prefers_codex_login(monkeypatch, capsys):
    monkeypatch.setenv("OPENAI_API_KEY", "x")
    monkeypatch.setattr(sys, "argv", ["main", "--scenario", "missing.json", "--out", "o"])
    from SDK import main as sdk_main
    with pytest.raises(Exception):  # stops later (no scenario file), not at the key check
        sdk_main.main()
    assert "OPENAI_API_KEY" not in os.environ
    assert "using your codex login" in capsys.readouterr().out


def test_mcp_server_returns_error_for_failing_tool(store):
    from SDK import mcp_server
    mcp_server.STORE = store
    tools = asyncio.run(mcp_server.list_tools())
    assert [t.name for t in tools] == list(tool_specs.SPECS)
    with pytest.raises(RuntimeError, match="Call search_jobs first"):
        asyncio.run(mcp_server.call_tool("track_job", {"job_id": "gh:x:1", "status": "saved"}))
    ok = asyncio.run(mcp_server.call_tool("get_tracker", {}))
    assert ok[0].text.startswith("{")
