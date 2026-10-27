import json

from API.harness import tools
from API.harness.tools import ToolExecutor
from shared import tool_specs


def call(name, args, call_id="call_1"):
    raw = args if isinstance(args, str) else json.dumps(args)
    return {"type": "function_call", "call_id": call_id, "name": name, "arguments": raw}


def test_schemas_come_from_the_shared_specs():
    s = tools.schemas()
    assert [t["name"] for t in s] == list(tool_specs.SPECS)
    assert all(t["type"] == "function" and t["strict"] is False and t["parameters"] for t in s)


def test_success_returns_output_item_for_the_same_call_id(store):
    out = ToolExecutor(store).run(call("get_tracker", {}, "call_9"))
    assert out["type"] == "function_call_output" and out["call_id"] == "call_9"
    assert json.loads(out["output"])  # compact JSON of the tool result


def test_unknown_tool_bad_args_and_exceptions_are_errors_not_crashes(store):
    ex = ToolExecutor(store)
    for c in (call("no_such_tool", {}), call("get_tracker", {"bogus": 1}), call("get_tracker", "{not json"),
              call("get_tracker", "[1]"), call("track_job", {"job_id": "gh:x:1", "status": "saved"})):
        body = json.loads(ex.run(c)["output"])
        assert body["is_error"] is True and body["error"]


def test_failures_are_written_to_the_tool_log(store):
    ToolExecutor(store).run(call("get_tracker", "{oops"))
    assert store.read_jsonl("tool_log.jsonl")[-1]["ok"] is False
