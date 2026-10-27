"""Prompt caching on OpenAI is automatic (prefix match, 1024+ tokens). This file keeps the prefix stable.

Rules: tools -> instructions -> history never change between calls, and the dynamic <context> lives in the
newest user item only (it is stored with that item, so later calls replay it byte-for-byte).
There is no cache write on OpenAI, so cache_write is always 0.
"""
import hashlib
import json

from . import items
from .config import HarnessConfig
from .logger import log
from .tokens import usage_of


def extras(model, config: HarnessConfig = HarnessConfig()):
    """Request fields that steer cache routing: the same key for every call of this agent."""
    return {"prompt_cache_key": f"{config.cache_key_prefix}-{model}"}


def _digest(obj):
    return hashlib.sha1(json.dumps(obj, sort_keys=True, ensure_ascii=False, default=str).encode()).hexdigest()[:10]


class PrefixMonitor:
    """Checks that each request starts with exactly the previous request, and logs cached tokens."""

    def __init__(self):
        self._static = self._input_digest = self._input_len = None

    def before_call(self, request):
        static = _digest([request.get("tools"), request.get("instructions")])
        messages = [items.plain(i) for i in request["input"]]
        if self._static is None:
            verdict = "first call of this agent"
        else:
            same = static == self._static and _digest(messages[:self._input_len]) == self._input_digest
            verdict = "prefix identical to the previous call" if same else "prefix CHANGED (cache will miss)"
        log(__file__, f"cache_key={request.get('prompt_cache_key')} static={static} {verdict}")
        self._static, self._input_digest, self._input_len = static, _digest(messages), len(messages)

    def after_call(self, resp):
        u = usage_of(resp)
        log(__file__, f"cached {u['cached']} of {u['input_total']} input tokens")
