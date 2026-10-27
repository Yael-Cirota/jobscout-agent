"""Whole scenario through the API agent: fake model, recorded board data, no key, no network."""
import dataclasses
import json
from pathlib import Path

import pytest

from API.agent import JobScoutAgent
from API.harness import items
from API.harness.config import HarnessConfig
from API.main import count_harness_loc
from shared import scenario_runner
from shared.store import Store
from tests.fake_client import FakeClient, call_response, text_response

SCENARIO = Path(__file__).resolve().parent.parent / "scenario.json"
HAIFA_ID = "gh:taboola:9900001"


class ScriptedModel:
    """Decides like a good model would: one tool round per turn, then a short answer."""

    def __init__(self, state_dir):
        self.state_dir = state_dir

    def __call__(self, request):
        if not request.get("tools"):                       # the summarizer call has no tools
            return text_response("Summary: searched, saved and applied to the JFrog job.")
        last = request["input"][-1]
        user = [i for i in request["input"] if items.is_user_turn(i)][-1]["content"].split("</context>\n")[-1]
        if items.kind(last) == "function_call_output":      # tools are done: answer
            return text_response(self._answer(user))
        return call_response([self._tool(user)])

    def _jfrog(self):
        known = Store(self.state_dir).known_jobs()
        return next(j for j, row in known.items() if "jfrog" in row["co"].lower())

    def _tool(self, user):
        if user.startswith("Find"):
            return "search_jobs", {"roles": ["backend"], "cities": ["Tel Aviv"], "limit": 20}
        if user.startswith("Save"):
            return "track_job", {"job_id": self._jfrog(), "status": "saved"}
        if user.startswith("I applied"):
            return "track_job", {"job_id": self._jfrog(), "status": "applied"}
        if user.startswith("Don't"):
            return "update_profile", {"reason": user, "cities": ["Tel Aviv"], "strict_cities": True}
        if user.startswith("What's"):
            return "get_tracker", {}
        if user.startswith("Anything"):
            return "search_jobs", {"only_new": True}
        if user.startswith("Show me"):
            return "get_job_details", {"job_id": HAIFA_ID}
        return "update_profile", {"reason": user, "cities": ["Tel Aviv", "Haifa"], "strict_cities": True}

    def _answer(self, user):
        if user.startswith("What's"):
            return "You applied to the JFrog job (applied)."
        if user.startswith("Show me"):
            return "It is in Haifa, outside your Tel Aviv rule. Add Haifa to your cities?"
        return "Done."


def run(tmp_path, monkeypatch, **cfg):
    monkeypatch.setenv("JOBSCOUT_HTTP", "replay")
    state = tmp_path / "state"
    store = Store(state)
    store.reset()
    client = FakeClient(ScriptedModel(state))
    config = dataclasses.replace(HarnessConfig(), **cfg)

    def make_agent(session):
        agent = JobScoutAgent(state, client, "gpt-test", "medium", config)
        agent.start_session(session)
        return agent

    out = tmp_path / "api.json"
    result = scenario_runner.run_scenario(scenario_runner.load_scenario(SCENARIO), store, make_agent,
                                          "api", out, {"billing": "openai-api"}, count_harness_loc())
    return result, state, client, json.loads(out.read_text(encoding="utf-8"))


def test_all_eight_checks_pass_and_results_have_every_field(tmp_path, monkeypatch):
    result, _, _, saved = run(tmp_path, monkeypatch)
    assert result["checks_passed"] == "8/8", [c for c in result["checks"] if not c["passed"]]
    for key in ("version", "model", "effort", "started_at", "turns", "totals", "checks", "loc"):
        assert key in saved
    assert [t["id"] for t in saved["turns"]] == [f"t{i}" for i in range(1, 9)]
    assert all(t["model_calls"] == 2 and len(t["tools"]) == 1 for t in saved["turns"])
    assert saved["loc"]["total"] > 0


def test_session_two_is_a_new_agent_that_starts_from_a_summary(tmp_path, monkeypatch):
    _, state, client, _ = run(tmp_path, monkeypatch)
    history = (state / "history" / "session.jsonl").read_text(encoding="utf-8").splitlines()
    records = [json.loads(ln) for ln in history]
    assert [r["type"] for r in records].count("compaction") == 2  # one forced summary per session
    first_t5_call = next(r for r in client.responses.requests
                         if "What's the status" in json.dumps(r["input"]))
    assert items.is_summary(first_t5_call["input"][0])           # session 1 arrives as a summary...
    assert len(first_t5_call["input"]) == 2                      # ...plus the new question, not session 1's items


def test_small_threshold_makes_compaction_fire_during_a_session(tmp_path, monkeypatch):
    result, state, _, _ = run(tmp_path, monkeypatch, compact_threshold=50, summarize_on_session_end=False)
    records = [json.loads(ln) for ln in (state / "history" / "session.jsonl").read_text(encoding="utf-8").splitlines()]
    assert any(r["type"] == "compaction" for r in records)
    assert result["checks_passed"] == "8/8"


def test_history_after_session_one_is_a_byte_prefix_of_the_final_file(tmp_path, monkeypatch):
    monkeypatch.setenv("JOBSCOUT_HTTP", "replay")
    state = tmp_path / "state"
    Store(state).reset()
    client, snapshots = FakeClient(ScriptedModel(state)), []
    store = Store(state)
    for session, turns in ((1, ["t1", "t2"]), (2, ["t5"])):
        agent = JobScoutAgent(state, client, "gpt-test", "medium")
        agent.start_session(session)
        for t in turns:
            store.set_turn(session, t)
            agent.ask({"t1": "Find me backend jobs in Tel Aviv.", "t2": "Save the JFrog one.",
                       "t5": "What's the status of my applications?"}[t])
        agent.end_session()
        snapshots.append((state / "history" / "session.jsonl").read_bytes())
    assert snapshots[1].startswith(snapshots[0]) and len(snapshots[1]) > len(snapshots[0])


def test_missing_key_stops_the_api_cli(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr("sys.argv", ["main", "--scenario", str(SCENARIO), "--out", "x.json"])
    from API import main as api_main
    monkeypatch.setattr(api_main, "load_dotenv", lambda *a, **k: None)  # ignore a real .env
    with pytest.raises(SystemExit, match="OPENAI_API_KEY"):
        api_main.main()
