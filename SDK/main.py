"""Run the JobScout scenario on the Codex SDK.

python SDK/main.py [--scenario scenario.json] [--out results/sdk.json]
"""
import argparse
import os
import sys
from importlib import metadata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from shared import scenario_runner  # noqa: E402
from shared.store import Store  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenario", help="replay the turns in this file (default: type them interactively; "
                                       "model and effort still come from scenario.json)")
    ap.add_argument("--out", help="result file (default: results/sdk_<timestamp>.json)")
    ap.add_argument("--state-dir", default="state/sdk")
    args = ap.parse_args()

    if os.environ.pop("OPENAI_API_KEY", None):  # the ChatGPT login wins; Codex inherits this environment
        print("[main.py] OPENAI_API_KEY ignored: using your codex login (ChatGPT Plus).")
    scenario = scenario_runner.load_scenario(args.scenario or ROOT / "scenario.json")
    if scenario["model"].startswith("REPLACE"):
        sys.exit("Set a real model in scenario.json (one that works in Codex with ChatGPT Plus AND in the API).")

    from SDK.agent import JobScoutSDKAgent  # imported late so the checks above run without the SDK
    http_mode = os.environ.get("JOBSCOUT_HTTP", "live")
    store = Store(args.state_dir)
    store.reset()  # clean state every run: wipe, recreate, seed companies
    print(f"[main.py] state={args.state_dir} http={http_mode} model={scenario['model']}")

    def make_agent(session):
        return JobScoutSDKAgent(args.state_dir, session, scenario["model"], scenario["effort"], http_mode)

    loc = scenario_runner.count_replaces(
        [ROOT / "SDK" / f for f in ("agent.py", "tools.py", "mcp_server.py")])
    loc["total"] = sum(loc.values())
    extra = {"library_versions": {"openai-codex": metadata.version("openai-codex"),
                                  "mcp": metadata.version("mcp")},
             "http_mode": http_mode, "billing": "chatgpt-plus (cost_usd is API-equivalent)"}
    out = args.out or scenario_runner.default_out_path("sdk")
    sessions = None if args.scenario else scenario_runner.interactive_sessions()
    scenario_runner.run_scenario(scenario, store, make_agent, "sdk", out, extra, loc, sessions)


if __name__ == "__main__":
    main()
