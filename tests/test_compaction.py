import dataclasses

from API.harness import items
from API.harness.compaction import Compactor, transcript
from API.harness.config import HarnessConfig
from API.harness.history import History
from API.harness.tokens import TokenTracker
from tests.fake_client import FakeClient, text_response
from tests.test_history import turn_items


def setup(tmp_path, turns, summary="SUMMARY", **cfg):
    config = dataclasses.replace(HarnessConfig(), **cfg)
    history = History(tmp_path)
    for n in range(1, turns + 1):
        history.append(1, f"t{n}", turn_items(n))
    client = FakeClient([text_response(summary)])
    return Compactor(client, "m", config, history, TokenTracker("m")), history, client


def test_triggers_only_above_the_threshold(tmp_path):
    c, _, _ = setup(tmp_path, 1, compact_threshold=2000)
    assert c.needed(2000) is False
    assert c.needed(2001) is True


def test_keeps_recent_turns_and_whole_call_pairs(tmp_path):
    c, history, client = setup(tmp_path, 4, keep_recent_turns=2)
    assert c.compact(1, "t4", "t4") is True
    view = history.messages()
    assert items.is_summary(view[0]) and view[1:] == turn_items(3) + turn_items(4)
    calls = {i["call_id"] for i in view if i.get("type") == "function_call"}
    outputs = {i["call_id"] for i in view if i.get("type") == "function_call_output"}
    assert calls == outputs  # no function_call separated from its output
    sent = client.responses.requests[0]["input"][0]["content"]
    assert "question 1" in sent and "question 2" in sent and "question 3" not in sent


def test_nothing_to_compact_when_too_few_turns(tmp_path):
    c, history, client = setup(tmp_path, 2, keep_recent_turns=2)
    assert c.compact(1, "t2", "t2") is False and client.responses.requests == []
    assert not history.has_summary()


def test_end_of_session_compaction_drops_everything_then_stacks(tmp_path):
    c, history, _ = setup(tmp_path, 2)
    assert c.compact(1, "t2", "end", keep_turns=0) is True
    assert history.messages() == [items.summary_item("SUMMARY")]
    assert c.compact(1, "t2", "end", keep_turns=0) is False  # only a summary left: nothing new to fold in
    history.append(2, "t3", turn_items(3))
    c.client.responses.script.append(text_response("SECOND"))
    assert c.compact(2, "t3", "end", keep_turns=0) is True
    assert "SUMMARY" in c.client.responses.requests[-1]["input"][0]["content"]  # old summary is carried over


def test_empty_summary_is_not_applied(tmp_path):
    c, history, _ = setup(tmp_path, 4, summary="   ")
    assert c.compact(1, "t4", "t4") is False and not history.has_summary()


def test_summary_call_is_recorded_in_the_token_tracker(tmp_path):
    c, _, _ = setup(tmp_path, 4)
    c.compact(1, "t4", "t4")
    assert c.tracker.summary("t4")["model_calls"] == 1


def test_transcript_skips_reasoning_and_truncates_outputs():
    msgs = [{"type": "reasoning", "encrypted_content": "x"},
            {"type": "function_call_output", "call_id": "c", "output": "y" * 50}] + turn_items(1)
    text = transcript(msgs, max_output_chars=10)
    assert "reasoning" not in text and "y" * 11 not in text and "assistant: answer 1" in text
