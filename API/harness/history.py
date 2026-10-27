"""Conversation saved to disk, append-only. Compaction adds a record; it never rewrites or deletes."""
import json
from pathlib import Path

from shared.store import now

from . import items
from .logger import log


class History:
    def __init__(self, state_dir, relative_path="history/session.jsonl"):
        self.path = Path(state_dir) / relative_path
        self._raw = []          # every item ever appended, in order
        self._summary = None    # text of the latest compaction
        self._keep_from = 0     # index into _raw where the verbatim part starts

    def load(self):
        """Rebuild the in-memory view from disk (start of a session)."""
        self._raw, self._summary, self._keep_from = [], None, 0
        if self.path.exists():
            for line in self.path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                rec = json.loads(line)
                if rec["type"] == "item":
                    self._raw.append(rec["item"])
                elif rec["type"] == "compaction":
                    self._summary, self._keep_from = rec["summary"], rec["keep_from"]
        log(__file__, f"loaded {len(self._raw)} items from {self.path.name}"
                      f"{' (with a compaction summary)' if self._summary else ''}")

    def messages(self):
        """What is sent to the model: [summary] + the items after the last compaction."""
        head = [items.summary_item(self._summary)] if self._summary else []
        return head + self._raw[self._keep_from:]

    def append(self, session, turn, new_items):
        plain = [items.plain(i) for i in new_items]
        self._write([{"type": "item", "session": session, "turn": turn, "item": i, "ts": now()} for i in plain])
        self._raw.extend(plain)
        log(__file__, f"appended {len(plain)} items -> {self.path.parent.name}/{self.path.name}")

    def compact(self, session, turn, summary, dropped):
        """Record a summary replacing the oldest `dropped` raw items of the current view."""
        self._keep_from += dropped
        self._summary = summary
        self._write([{"type": "compaction", "session": session, "turn": turn, "summary": summary,
                      "keep_from": self._keep_from, "ts": now()}])

    def has_summary(self):
        return self._summary is not None

    def _write(self, records):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "a", encoding="utf-8") as f:  # append mode only: earlier bytes never change
            for rec in records:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
