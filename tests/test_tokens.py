import pytest

from API.harness import items
from API.harness.tokens import TokenTracker, usage_of
from shared import pricing
from tests.fake_client import text_response


@pytest.fixture(autouse=True)
def fixed_prices(monkeypatch):
    monkeypatch.setitem(pricing.PRICES, "m", {"input": 1.0, "cached_input": 0.1, "output": 10.0})


def test_usage_normalizes_dict_and_object_shapes():
    resp = text_response("hi", input_tokens=500, cached=200, output=40, reasoning=15)
    assert usage_of(resp) == {"input_total": 500, "cached": 200, "output": 40, "reasoning": 15}
    assert usage_of(type("R", (), {"usage": None})())["input_total"] == 0


def test_turn_sums_over_calls_and_splits_cached_input():
    t = TokenTracker("m")
    t.record("t1", text_response("a", input_tokens=1000, cached=0, output=50), 1.0)
    t.record("t1", text_response("b", input_tokens=1200, cached=1000, output=30), 2.0)
    t.record("t2", text_response("c", input_tokens=9, cached=0, output=1), 1.0)
    s = t.summary("t1")
    assert s["tokens"] == {"input": 1200, "cache_read": 1000, "cache_write": 0, "output": 80}
    assert s["model_calls"] == 2 and s["time_s"] == 3.0
    # 1200 uncached*1 + 1000 cached*0.1 + 80 out*10 = 2100 per million
    assert s["cost_usd"] == pytest.approx(0.0021)


def test_unknown_model_cost_is_none_not_a_guess():
    t = TokenTracker("no-such-model")
    t.record("t1", text_response("a"), 0.5)
    assert t.summary("t1")["cost_usd"] is None


def test_last_context_tokens_and_wall_time_override():
    t = TokenTracker("m")
    t.record("t1", text_response("a", input_tokens=10), 1)
    t.record("t1", text_response("b", input_tokens=77), 1)
    assert t.last_context_tokens("t1") == 77 and t.last_context_tokens("nope") == 0
    assert t.summary("t1", wall_seconds=9.123)["time_s"] == 9.12


def test_items_helpers():
    assert items.is_user_turn(items.user_item("hello"))
    assert items.is_summary(items.summary_item("x")) and not items.is_user_turn(items.summary_item("x"))
    out = text_response("answer").output
    assert items.output_text(out) == "answer" and items.function_calls(out) == []
