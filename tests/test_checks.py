import copy

from shared import checks


def snap(cities=("Tel Aviv",), strict=True, changes=1, tracker=None, seen=()):
    return {"profile": {"cities": list(cities), "strict_cities": strict, "changes": [{}] * changes},
            "tracker": {"jobs": tracker or {}}, "seen": {i: "x" for i in seen}}


APPLIED = {"gh:lightrun:1": {"company": "JFrog", "status": "applied",
                             "history": [{"status": "saved"}, {"status": "applied"}]}}


def good():
    return {
        "snaps": {"t3": snap(tracker=APPLIED), "t4": snap(seen=["a", "b"]), "t7": snap(),
                  "t8": snap(cities=("Tel Aviv", "Haifa"), changes=2)},
        "tool_log": [
            {"turn": "t1", "tool": "search_jobs", "ids": ["a", "b"], "has_description": False},
            {"turn": "t6", "tool": "search_jobs", "ids": ["c"], "has_description": False},
            {"turn": "t7", "tool": "get_job_details"}],
        "http_log": [{"turn": "t1", "url": "https://boards-api.greenhouse.io/x"},
                     {"turn": "t6", "url": "https://api.lever.co/y"}],
        "answers": {"t5": "JFrog - applied", "t7": "Your profile says Tel Aviv only. Add Haifa?"},
        "instances": {1: "A@1", 2: "A@2"}, "target_company": "JFrog", "details_turns": ["t7"]}


def passed(ctx):
    return {c["id"]: c["passed"] for c in checks.run_checks(ctx)}


def test_all_pass_on_good_state():
    assert all(passed(good()).values())


def test_each_check_fails_on_bad_state():
    bad = {}
    c = good(); c["snaps"]["t3"] = snap(tracker={}); bad["C1"] = c
    c = good(); c["snaps"]["t4"] = snap(strict=False); bad["C2"] = c
    c = good(); c["snaps"]["t4"] = snap(seen=["a", "b", "c"]); bad["C3"] = c
    c = good(); c["http_log"] = []; bad["C4"] = c
    c = good(); c["instances"] = {1: "A@1", 2: "A@1"}; bad["C5"] = c
    c = good(); c["snaps"]["t7"] = snap(cities=("Tel Aviv", "Haifa")); bad["C6"] = c
    c = good(); c["snaps"]["t8"] = snap(cities=("Tel Aviv",), changes=1); bad["C7"] = c
    c = good(); c["tool_log"].append({"turn": "t1", "tool": "get_job_details"}); bad["C8"] = c
    for cid, ctx in bad.items():
        assert passed(ctx)[cid] is False, cid


def test_missing_snapshot_is_a_failed_check_not_a_crash():
    ctx = copy.deepcopy(good()); del ctx["snaps"]["t8"]
    assert passed(ctx)["C7"] is False
