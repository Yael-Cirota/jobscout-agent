from API.harness import caching, items, loop, logger
from API.harness.config import HarnessConfig
from tests.fake_client import FakeClient, call_response, text_response
from tests.test_loop import EchoExecutor


def capture():
    lines = []
    logger.set_sink(lines.append)
    return lines


def test_extras_set_a_stable_cache_key():
    assert caching.extras("m") == caching.extras("m") == {"prompt_cache_key": "jobscout-m"}
    assert caching.extras("m", HarnessConfig(cache_key_prefix="x")) == {"prompt_cache_key": "x-m"}


def request(messages, **kw):
    return {"model": "m", "instructions": "sys", "tools": [{"name": "t"}], "input": messages, **kw}


def test_monitor_reports_identical_prefix_when_history_only_grows():
    lines = capture()
    mon = caching.PrefixMonitor()
    a = [items.user_item("<context>\nx\n</context>\nfirst")]
    mon.before_call(request(a))
    mon.before_call(request(a + [{"type": "message", "role": "assistant", "content": []},
                                 items.user_item("<context>\ny\n</context>\nsecond")]))
    assert "first call" in lines[0] and "prefix identical" in lines[1]


def test_monitor_flags_an_edited_earlier_item_or_changed_instructions():
    lines = capture()
    mon = caching.PrefixMonitor()
    mon.before_call(request([items.user_item("a")]))
    mon.before_call(request([items.user_item("CHANGED"), items.user_item("b")]))
    mon.before_call(request([items.user_item("CHANGED"), items.user_item("b"), items.user_item("c")],
                            instructions="other"))
    assert "CHANGED" in lines[1] and "CHANGED" in lines[2]


def test_every_call_in_a_tool_loop_shares_the_key_and_prefix():
    lines = capture()
    client, mon = FakeClient([call_response([("get_tracker", {})]), text_response("ok")]), caching.PrefixMonitor()
    loop.run_turn(client, request([], **caching.extras("m")), [items.user_item("hi")], EchoExecutor(), 10,
                  on_request=mon.before_call, on_response=lambda r, s: mon.after_call(r))
    keys = {r["prompt_cache_key"] for r in client.responses.requests}
    assert keys == {"jobscout-m"}
    assert any("prefix identical" in ln for ln in lines) and not any("CHANGED" in ln for ln in lines)
    assert any("cached 0 of 100" in ln for ln in lines)
