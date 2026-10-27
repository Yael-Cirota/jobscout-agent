"""A scripted stand-in for `openai.OpenAI().responses`. Records every request it receives."""
from types import SimpleNamespace


def usage(input_tokens=100, cached=0, output=20, reasoning=0, cache_write=0):
    return {"input_tokens": input_tokens,
            "input_tokens_details": {"cached_tokens": cached, "cache_write_tokens": cache_write},
            "output_tokens": output, "output_tokens_details": {"reasoning_tokens": reasoning}}


def text_response(text, **u):
    msg = {"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": text}]}
    return SimpleNamespace(output=[msg], usage=usage(**u))


def call_response(calls, **u):
    """calls: [(name, args_dict_or_raw_string)] -> one response holding a reasoning item + those calls."""
    import json
    out = [{"type": "reasoning", "id": "rs_1", "summary": [], "encrypted_content": "enc"}]
    for n, (name, args) in enumerate(calls, 1):
        raw = args if isinstance(args, str) else json.dumps(args)
        out.append({"type": "function_call", "call_id": f"call_{n}", "name": name, "arguments": raw})
    return SimpleNamespace(output=out, usage=usage(**u))


class FakeResponses:
    """`script` is a list of responses, or a callable(request) -> response."""

    def __init__(self, script):
        self.script, self.requests = script, []

    def create(self, **kwargs):
        # snapshot: the loop keeps mutating its own list after the call
        self.requests.append({**kwargs, "input": list(kwargs.get("input", []))})
        if callable(self.script):
            return self.script(kwargs)
        if not self.script:
            raise AssertionError("FakeResponses: script exhausted")
        return self.script.pop(0)


class FakeClient:
    def __init__(self, script):
        self.responses = FakeResponses(script)
