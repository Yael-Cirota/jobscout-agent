"""Scenario loading + running, snapshots, LOC counting. Used by both main.py files.

Turns come from the scenario file (scripted) or are typed at a prompt (interactive_sessions).
An agent must provide:  ask(text) -> TurnResult-dict  and  end_session().
TurnResult dict: {"answer", "tokens": {"input","cache_read","cache_write","output"},
                  "model_calls", "tools": [names], "cost_usd", "time_s"}
"""
import itertools
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path

from . import checks
from .store import Store


def load_scenario(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def count_loc(path):
    """Non-blank, non-comment lines."""
    n = 0
    for ln in Path(path).read_text(encoding="utf-8").splitlines():
        s = ln.strip()
        if s and not s.startswith("#"):
            n += 1
    return n


def count_replaces(paths):
    """Count code lines marked `# replaces: a, b` grouped by part name."""
    out = {}
    for p in paths:
        for ln in Path(p).read_text(encoding="utf-8").splitlines():
            m = re.search(r"#\s*replaces:\s*([\w, ]+)", ln)
            if m and ln.strip() and not ln.strip().startswith("#"):
                for part in (x.strip() for x in m.group(1).split(",")):
                    out[part] = out.get(part, 0) + 1
    return out


def _totals(turns):
    tok = {k: sum(t["tokens"][k] for t in turns) for k in ("input", "cache_read", "cache_write", "output")}
    denom = tok["input"] + tok["cache_read"] + tok["cache_write"]
    costs = [t["cost_usd"] for t in turns]
    return {"tokens": tok, "cache_pct": round(100 * tok["cache_read"] / denom, 1) if denom else 0.0,
            "model_calls": sum(t["model_calls"] for t in turns),
            "cost_usd": None if None in costs else round(sum(costs), 6),
            "time_s": round(sum(t["time_s"] for t in turns), 1)}


def default_out_path(version):
    """A fresh results/<version>_<timestamp>.json per run, so runs never overwrite each other."""
    return Path("results") / f"{version}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"


def scripted_sessions(scenario):
    """The turns written in the scenario file, as (session, [(turn_id, text), ...]) pairs."""
    for sess in scenario["sessions"]:
        yield sess["session"], [(t["id"], t["text"]) for t in sess["turns"]]


def interactive_sessions():
    """Turns typed at a prompt. /new starts the next session (a new agent instance), /quit ends the run.
    Turn ids run t1, t2, ... across sessions, like the scripted scenario, so the checks still apply."""
    print("[scenario] interactive: type a message, /new for a new session, /quit to finish")
    turn_ids = (f"t{i}" for i in itertools.count(1))
    done = False

    def turns():
        nonlocal done
        while True:
            try:
                text = input("you> ").strip()
            except (EOFError, KeyboardInterrupt):
                text = "/quit"
            if text in ("/new", "/quit"):
                done = text == "/quit"
                return
            if text:
                yield next(turn_ids), text

    for session in itertools.count(1):
        yield session, turns()
        if done:
            return


def run_scenario(scenario, store, make_agent, version, out_path, extra=None, loc=None, sessions=None):
    """make_agent(session_number) -> a NEW agent object each call (session 2 = new instance).
    sessions: (session, turns) pairs to run instead of the scenario's own turns (see interactive_sessions)."""
    interactive = sessions is not None
    out_path = Path(out_path)
    snap_dir = out_path.parent / f"{out_path.stem}_snapshots"
    snap_dir.mkdir(parents=True, exist_ok=True)
    started = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    turns, snaps, answers, instances = [], {}, {}, {}

    for n, session_turns in sessions or scripted_sessions(scenario):
        agent = make_agent(n)
        instances[n] = f"{type(agent).__name__}@{id(agent)}"
        print(f"[scenario] session {n} started, instance={instances[n]}")
        for tid, text in session_turns:
            store.set_turn(n, tid)
            t0 = time.time()
            r = agent.ask(text)
            r.setdefault("time_s", round(time.time() - t0, 2))
            answers[tid] = r["answer"]
            snaps[tid] = store.snapshot()
            (snap_dir / f"after_{tid}.json").write_text(
                json.dumps(snaps[tid], indent=2, ensure_ascii=False), encoding="utf-8")
            turns.append({"session": n, "id": tid, "text": text, "tokens": r["tokens"],
                          "model_calls": r["model_calls"], "tools": r["tools"],
                          "cost_usd": r["cost_usd"], "time_s": r["time_s"]})
            if interactive:
                print(f"jobscout> {r['answer']}\n")
            print(f"[scenario] {tid}: tools={r['tools']} calls={r['model_calls']} "
                  f"in={r['tokens']['input']} out={r['tokens']['output']}")
        agent.end_session()

    ctx = {"snaps": snaps, "tool_log": store.read_jsonl("tool_log.jsonl"),
           "http_log": store.read_jsonl("http_log.jsonl"), "answers": answers, "instances": instances,
           "target_company": scenario.get("target_company", "Lightrun"),
           "details_turns": scenario.get("details_turns", ["t7"])}
    results = checks.run_checks(ctx, scenario.get("checks"))
    passed = sum(c["passed"] for c in results)
    result = {"version": version, "mode": "interactive" if interactive else "scripted",
              "model": scenario["model"], "effort": scenario["effort"], **(extra or {}), "started_at": started, "turns": turns, "totals": _totals(turns),
              "checks": results, "checks_passed": f"{passed}/{len(results)}", "loc": loc or {}}
    out_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    for c in results:
        print(f"[checks] {c['id']} {'PASS' if c['passed'] else 'FAIL'} - {c['detail']}")
    print(f"[checks] {passed}/{len(results)} passed -> {out_path}")
    return result
