"""JSON persistence for profile, companies, tracker, seen, known jobs, and logs."""
import copy
import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path

from .http_client import HttpClient

SEED = Path(__file__).parent / "data" / "companies.seed.json"
DEFAULT_PROFILE = {"roles": [], "cities": [], "strict_cities": False, "skip_companies": [],
                   "seniority": None, "updated_at": None, "changes": []}


def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class Store:
    def __init__(self, state_dir, http=None):
        self.dir = Path(state_dir)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.http = http or HttpClient(self.dir / "http_log.jsonl", turn_getter=self.current_turn)

    # --- generic helpers -------------------------------------------------
    def _read(self, name, default):
        p = self.dir / name
        if not p.exists():
            return default
        return json.loads(p.read_text(encoding="utf-8"))

    def _write(self, name, data):
        p = self.dir / name
        tmp = p.with_suffix(p.suffix + ".tmp")
        tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, p)

    def reset(self):
        """Wipe the state dir, recreate it and seed the company list."""
        shutil.rmtree(self.dir, ignore_errors=True)
        self.dir.mkdir(parents=True)
        self.http.log_path = self.dir / "http_log.jsonl"
        self.http.cache.clear()
        self._write("companies.json", json.loads(SEED.read_text(encoding="utf-8")))

    # --- domain data -----------------------------------------------------
    def profile(self):
        return {**copy.deepcopy(DEFAULT_PROFILE), **self._read("profile.json", {})}

    def save_profile(self, p):
        self._write("profile.json", p)

    def companies(self):
        return self._read("companies.json", [])

    def save_companies(self, c):
        self._write("companies.json", c)

    def tracker(self):
        return self._read("tracker.json", {"jobs": {}})

    def save_tracker(self, t):
        self._write("tracker.json", t)

    def seen(self):
        return self._read("seen.json", {"seen": {}})["seen"]

    def mark_seen(self, ids):
        s = self.seen()
        for i in ids:
            s.setdefault(i, now())
        self._write("seen.json", {"seen": s})

    def known_jobs(self):
        """Short rows of jobs shown to the user (id -> title/company/city/url)."""
        return self._read("known_jobs.json", {})

    def remember_jobs(self, rows):
        k = self.known_jobs()
        k.update({r["id"]: r for r in rows})
        self._write("known_jobs.json", k)

    # --- turn marker + logs (shared between processes via a file) --------
    def set_turn(self, session, turn_id):
        self._write("turn.json", {"session": session, "turn": turn_id})

    def current_turn(self):
        return self._read("turn.json", {}).get("turn")

    def log_tool(self, entry):
        entry = {"ts": now(), "turn": self.current_turn(), **entry}
        with open(self.dir / "tool_log.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def read_jsonl(self, name):
        p = self.dir / name
        if not p.exists():
            return []
        return [json.loads(ln) for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip()]

    def snapshot(self):
        return {"profile": self.profile(), "tracker": self.tracker(), "seen": self.seen()}

    # --- one-line summaries used for context -----------------------------
    def tracker_summary(self):
        jobs = self.tracker()["jobs"]
        if not jobs:
            return "tracker: empty"
        counts = {}
        for j in jobs.values():
            counts[j["status"]] = counts.get(j["status"], 0) + 1
        latest = sorted(jobs.values(), key=lambda j: j["history"][-1]["at"], reverse=True)[:3]
        last = "; ".join(f'{j["company"]} "{j["title"]}" ({j["status"]}, {j["history"][-1]["at"][:10]})'
                         for j in latest)
        c = " · ".join(f"{k}={v}" for k, v in counts.items())
        return f"tracker: {len(jobs)} job{'s' if len(jobs) != 1 else ''} · {c} · latest: {last}"

    def profile_slice(self, fields):
        p = self.profile()
        return " ".join(f"{k}={json.dumps(p[k], ensure_ascii=False)}" for k in fields if k in p)
