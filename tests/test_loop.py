from API.harness import items, loop
from tests.fake_client import FakeClient, call_response, text_response

REQUEST = {"model": "m", "instructions": "sys", "tools": [], "store": False}


class EchoExecutor:
    def __init__(self):
        self.ran = []

    def run(self, call):
        self.ran.append(call["name"])
        return items.call_output_item(call["call_id"], "{}")


def go(script, max_calls=10, **kw):
    client, ex = FakeClient(script), EchoExecutor()
    out = loop.run_turn(client, REQUEST, [items.user_item("hi")], ex, max_calls, **kw)
    return out, client, ex


def test_stops_on_a_plain_answer():
    out, client, _ = go([text_response("done")])
    assert out.text == "done" and out.calls == 1 and out.tools == [] and not out.capped
    assert len(client.responses.requests) == 1


def test_continues_while_there_are_function_calls():
    out, client, ex = go([call_response([("get_tracker", {})]), text_response("ok")])
    assert out.calls == 2 and ex.ran == ["get_tracker"] and out.tools == ["get_tracker"]
    second = client.responses.requests[1]["input"]
    kinds = [items.kind(i) for i in second]
    assert kinds == ["message", "reasoning", "function_call", "function_call_output"]  # reasoning is passed back


def test_two_function_calls_come_back_in_one_batch():
    out, client, ex = go([call_response([("get_tracker", {}), ("get_profile", {})]), text_response("ok")])
    outputs = [i for i in client.responses.requests[1]["input"] if items.kind(i) == "function_call_output"]
    assert [o["call_id"] for o in outputs] == ["call_1", "call_2"]
    assert ex.ran == ["get_tracker", "get_profile"] and len(client.responses.requests) == 2
    # the two outputs sit right after the two calls, with no model call in between
    kinds = [items.kind(i) for i in client.responses.requests[1]["input"]]
    assert kinds[-2:] == ["function_call_output", "function_call_output"]


def test_safety_cap_stops_and_keeps_calls_paired():
    script = [call_response([("get_tracker", {})]) for _ in range(5)]
    out, client, ex = go(script, max_calls=3)
    assert out.capped and out.calls == 3 and len(client.responses.requests) == 3
    assert len(ex.ran) == 2  # the third round was refused, not executed
    calls = [i["call_id"] for i in out.new_items if items.kind(i) == "function_call"]
    outputs = [i["call_id"] for i in out.new_items if items.kind(i) == "function_call_output"]
    assert len(calls) == len(outputs) == 3


def test_hooks_see_every_request_and_response():
    seen = {"req": 0, "resp": 0}
    go([call_response([("get_tracker", {})]), text_response("ok")],
       on_request=lambda r: seen.__setitem__("req", seen["req"] + 1),
       on_response=lambda r, s: seen.__setitem__("resp", seen["resp"] + 1))
    assert seen == {"req": 2, "resp": 2}


def test_requests_are_snapshots_and_fixed_fields_are_forwarded():
    _, client, _ = go([call_response([("get_tracker", {})]), text_response("ok")])
    first, second = client.responses.requests
    assert len(first["input"]) == 1 and len(second["input"]) == 4
    assert first["model"] == "m" and first["store"] is False and first["instructions"] == "sys"
