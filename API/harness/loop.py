"""The agent loop: call the model, run every function call, send all outputs back together, repeat."""
import time
from dataclasses import dataclass, field

from . import items
from .logger import log


@dataclass
class TurnOutcome:
    new_items: list = field(default_factory=list)   # everything the turn added after the user item
    text: str = ""
    tools: list = field(default_factory=list)       # names of the tools called, in order
    calls: int = 0
    capped: bool = False


def _noop(*_):
    pass


def run_turn(client, request, messages, executor, max_calls, on_request=_noop, on_response=_noop):
    """`request` holds the fixed fields (model, instructions, tools, ...); `messages` ends with the user item.

    on_request(request) and on_response(resp, seconds) let other parts (caching, tokens) observe each call.
    """
    working, out = list(messages), TurnOutcome()
    while True:
        out.calls += 1
        full = {**request, "input": list(working)}
        on_request(full)
        started = time.time()
        resp = client.responses.create(**full)
        on_response(resp, round(time.time() - started, 2))

        produced = [items.plain(i) for i in resp.output]
        calls = items.function_calls(produced)
        log(__file__, f"call #{out.calls} -> {len(calls)} function call(s)" if calls
                      else f"call #{out.calls} -> final answer")
        working += produced
        out.new_items += produced
        if not calls:
            out.text = items.output_text(produced)
            return out

        out.tools += [c["name"] for c in calls]
        if out.calls >= max_calls:
            # keep every call paired with an output so the saved history stays valid, then stop
            outputs = [items.call_output_item(c["call_id"], '{"error":"call limit reached","is_error":true}')
                       for c in calls]
            out.capped = True
            log(__file__, f"safety cap of {max_calls} model calls reached, stopping the turn")
        else:
            outputs = [executor.run(c) for c in calls]
        working += outputs          # ONE batch holding all the outputs of this round
        out.new_items += outputs
        if out.capped:
            return out
