"""Summarize the conversation once it grows past a threshold (or at the end of a session)."""
import json
import time

from . import items
from .config import HarnessConfig
from .history import History
from .logger import log
from .tokens import TokenTracker


def transcript(messages, max_output_chars):
    """Plain-text rendering of items for the summarizer (no reasoning items, short tool outputs)."""
    lines = []
    for m in messages:
        k = items.kind(m)
        if k == "message":
            text = items.get(m, "content")
            if not isinstance(text, str):
                text = "".join(items.get(c, "text", "") for c in text or [])
            lines.append(f"{items.get(m, 'role', 'assistant')}: {text}")
        elif k == "function_call":
            lines.append(f"tool call {items.get(m, 'name')}({items.get(m, 'arguments')})")
        elif k == "function_call_output":
            lines.append(f"tool output: {str(items.get(m, 'output'))[:max_output_chars]}")
    return "\n".join(lines)


class Compactor:
    def __init__(self, client, model, config: HarnessConfig, history: History, tracker: TokenTracker):
        self.client, self.model, self.config = client, model, config
        self.history, self.tracker = history, tracker

    def needed(self, context_tokens):
        below = context_tokens <= self.config.compact_threshold
        if below:
            log(__file__, f"context {context_tokens} tokens <= threshold {self.config.compact_threshold}, "
                          "no compaction")
        return not below

    def cut_point(self, keep_turns):
        """Index in the current view where the verbatim part starts, or None if nothing can be dropped.

        Always a user-turn boundary, so a function_call is never separated from its output.
        """
        view = self.history.messages()
        starts = [i for i, m in enumerate(view) if items.is_user_turn(m)]
        if keep_turns == 0:
            cut = len(view)
        elif len(starts) > keep_turns:
            cut = starts[-keep_turns]
        else:
            return None
        has_summary = bool(view) and items.is_summary(view[0])
        return cut if cut > (1 if has_summary else 0) else None

    def compact(self, session, turn, bucket, keep_turns=None):
        keep = self.config.keep_recent_turns if keep_turns is None else keep_turns
        cut = self.cut_point(keep)
        if cut is None:
            log(__file__, "nothing to compact yet")
            return False
        view = self.history.messages()
        text = self._summarize(view[:cut], bucket)
        if not text:
            log(__file__, "summary came back empty, keeping the history as it is")
            return False
        dropped = cut - (1 if items.is_summary(view[0]) else 0)
        self.history.compact(session, turn, text, dropped)
        log(__file__, f"compacted {cut} msgs -> 1 summary ({len(text)} chars), kept {len(view) - cut} msgs")
        return True

    def _summarize(self, old, bucket):
        started = time.time()
        resp = self.client.responses.create(
            model=self.model, instructions=self.config.summary_instructions,
            input=[items.user_item(transcript(old, self.config.transcript_output_chars))],
            reasoning={"effort": self.config.summary_effort}, store=False)
        self.tracker.record(bucket, resp, round(time.time() - started, 2))
        return items.output_text(resp.output).strip()
