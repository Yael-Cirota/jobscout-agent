"""Run the JobScout scenario on the raw OpenAI API (hand-written harness).

python API/main.py --scenario scenario.json [--out results/api.json] [--compact-threshold 2000]
"""
import argparse
import dataclasses
import json
import os
import sys
from importlib import metadata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

from API.agent import JobScoutAgent  # noqa: E402
from API.harness.config import HarnessConfig  # noqa: E402
from shared import scenario_runner  # noqa: E402
from shared.store import Store  # noqa: E402

HARNESS_DIR = ROOT / "API" / "harness"


def count_harness_loc():
    """Non-blank, non-comment lines per harness file (each file is one part), plus agent + main."""
    loc = {p.stem: scenario_runner.count_loc(p) for p in sorted(HARNESS_DIR.glob("*.py"))}
    loc["agent+main"] = sum(scenario_runner.count_loc(ROOT / "API" / f) for f in ("agent.py", "main.py"))
    loc["total"] = sum(loc.values())
    return loc


def add_session_end_usage(out_path, agents):
    """The end-of-session summaries happen outside any turn, so they are reported next to the totals."""
    path = Path(out_path)
    result = json.loads(path.read_text(encoding="utf-8"))
    result["session_end_summaries"] = {str(a.session): a.session_end for a in agents if a.session_end}
    path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenario", required=True)
    ap.add_argument("--out", help="result file (default: results/api_<timestamp>.json)")
    ap.add_argument("--state-dir", default="state/api")
    ap.add_argument("--compact-threshold", type=int, default=HarnessConfig().compact_threshold)
    args = ap.parse_args()

    load_dotenv(ROOT / ".env")  # a real environment variable still wins over the file
    if not os.environ.get("OPENAI_API_KEY"):
        sys.exit("[main.py] OPENAI_API_KEY is not set (environment or .env). The API version needs it (the SDK version uses codex login).")
    scenario = scenario_runner.load_scenario(args.scenario)
    config = dataclasses.replace(HarnessConfig(), compact_threshold=args.compact_threshold)

    from openai import OpenAI  # imported late so the checks above run without the package
    client = OpenAI()
    http_mode = os.environ.get("JOBSCOUT_HTTP", "live")
    store = Store(args.state_dir)
    store.reset()  # clean state every run: wipe, recreate, seed companies
    print(f"[main.py] state={args.state_dir} http={http_mode} model={scenario['model']} "
          f"compact_threshold={config.compact_threshold}")

    agents = []

    def make_agent(session):
        agent = JobScoutAgent(args.state_dir, client, scenario["model"], scenario["effort"], config)
        agent.start_session(session)
        agents.append(agent)
        return agent

    extra = {"library_versions": {"openai": metadata.version("openai")}, "http_mode": http_mode,
             "billing": "openai-api", "compact_threshold": config.compact_threshold}
    out = args.out or scenario_runner.default_out_path("api")
    scenario_runner.run_scenario(scenario, store, make_agent, "api", out, extra, count_harness_loc())
    add_session_end_usage(out, agents)


if __name__ == "__main__":
    main()
