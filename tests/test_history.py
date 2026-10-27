import json

from API.harness import items
from API.harness.history import History


def turn_items(n):
    return [items.user_item(f"question {n}"),
            {"type": "function_call", "call_id": f"c{n}", "name": "get_tracker", "arguments": "{}"},
            {"type": "function_call_output", "call_id": f"c{n}", "output": "{}"},
            {"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": f"answer {n}"}]}]


def test_append_only_file_only_grows(tmp_path):
    h = History(tmp_path)
    h.append(1, "t1", turn_items(1))
    before = h.path.read_bytes()
    h.append(1, "t2", turn_items(2))
    h.compact(1, "t2", "summary", dropped=4)
    after = h.path.read_bytes()
    assert after.startswith(before) and len(after) > len(before)


def test_reload_rebuilds_the_same_messages(tmp_path):
    h = History(tmp_path)
    h.append(1, "t1", turn_items(1))
    h.append(1, "t2", turn_items(2))
    fresh = History(tmp_path)
    fresh.load()
    assert fresh.messages() == h.messages() == turn_items(1) + turn_items(2)


def test_compaction_is_a_record_and_the_view_is_summary_plus_tail(tmp_path):
    h = History(tmp_path)
    h.append(1, "t1", turn_items(1))
    h.append(1, "t2", turn_items(2))
    h.compact(1, "t2", "S1", dropped=4)
    lines = [json.loads(ln) for ln in h.path.read_text().splitlines()]
    assert [r["type"] for r in lines].count("item") == 8 and lines[-1]["type"] == "compaction"
    assert lines[-1]["keep_from"] == 4  # nothing was deleted, the earlier items are still in the file
    assert h.messages() == [items.summary_item("S1")] + turn_items(2)

    h.append(2, "t3", turn_items(3))
    h.compact(2, "t3", "S2", dropped=4)  # second compaction: keep_from accumulates over raw items
    fresh = History(tmp_path)
    fresh.load()
    assert fresh.messages() == [items.summary_item("S2")] + turn_items(3)
    assert fresh.has_summary()


def test_sdk_objects_are_stored_as_plain_json(tmp_path):
    class Obj:
        def model_dump(self, exclude_none=False):
            return {"type": "reasoning", "id": "rs_1", "summary": []}
    h = History(tmp_path)
    h.append(1, "t1", [Obj()])
    assert json.loads(h.path.read_text())["item"]["type"] == "reasoning"
