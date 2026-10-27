"""Read side of the persisted memory (profile, tracker, seen jobs). Writes happen inside the shared tools."""
import json

from .logger import log


class Memory:
    def __init__(self, store):
        self.store = store

    def load_all(self):
        p, t, s = self.store.profile(), self.store.tracker()["jobs"], self.store.seen()
        log(__file__, f"loaded profile ({len(p)} fields), tracker ({len(t)} jobs), seen ({len(s)})")
        return {"profile": p, "tracker": t, "seen": s}

    def profile_slice(self, fields):
        """`k=json` pairs for the wanted fields. `name:N` keeps the last N items of a list field."""
        profile, parts = self.store.profile(), []
        for spec in fields:
            name, _, count = spec.partition(":")
            if name not in profile:
                continue
            value = profile[name][-int(count):] if count else profile[name]
            parts.append(f"{name}={json.dumps(value, ensure_ascii=False)}")
        return " ".join(parts)

    def tracker_summary(self):
        return self.store.tracker_summary()

    def seen_ids(self):
        return set(self.store.seen())

    def snapshot(self):
        return self.store.snapshot()
