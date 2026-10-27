"""Token usage and cost per bucket (a turn id, or any label), summed over its model calls."""
from shared import pricing

from . import items
from .logger import log


def usage_of(resp):
    """Normalize a Responses API usage block. OpenAI counts cached tokens inside input_tokens."""
    u = items.get(resp, "usage") or {}
    return {"input_total": items.get(u, "input_tokens", 0) or 0,
            "cached": items.get(items.get(u, "input_tokens_details") or {}, "cached_tokens", 0) or 0,
            "output": items.get(u, "output_tokens", 0) or 0,
            "reasoning": items.get(items.get(u, "output_tokens_details") or {}, "reasoning_tokens", 0) or 0}


class TokenTracker:
    def __init__(self, model):
        self.model = model
        self.calls = []   # {"bucket", "seconds", **usage_of}

    def record(self, bucket, resp, seconds):
        usage = usage_of(resp)
        self.calls.append({"bucket": bucket, "seconds": seconds, **usage})
        log(__file__, f"{bucket}: call in={usage['input_total']} cached={usage['cached']} "
                      f"out={usage['output']} (reasoning {usage['reasoning']})")

    def last_context_tokens(self, bucket):
        """Input size of the most recent call in a bucket (what compaction compares to its threshold)."""
        mine = [c for c in self.calls if c["bucket"] == bucket]
        return mine[-1]["input_total"] if mine else 0

    def summary(self, bucket, wall_seconds=None):
        mine = [c for c in self.calls if c["bucket"] == bucket]
        total = {k: sum(c[k] for c in mine) for k in ("input_total", "cached", "output")}
        # OpenAI has no cache-write charge: cache_write is always 0 (kept for the shared result shape)
        tokens = {"input": total["input_total"] - total["cached"], "cache_read": total["cached"],
                  "cache_write": 0, "output": total["output"]}
        return {"tokens": tokens, "model_calls": len(mine),
                "cost_usd": pricing.cost_usd(self.model, total["input_total"], total["cached"], total["output"]),
                "time_s": round(wall_seconds if wall_seconds is not None else sum(c["seconds"] for c in mine), 2)}
