import json

import pytest

from shared import tools_impl as T


def ids(out):
    return [j["id"] for j in out["jobs"]]


def test_search_filters_israel_city_role(store):
    out = T.search_jobs(store, roles=["backend"], cities=["Tel Aviv"])
    assert set(ids(out)) == {"gh:acme:1", "gh:acme:3", "lv:lvco:ab12"}  # no NY, no sales, no frontend
    assert [o["id"] for o in out["outside_cities"]] == ["gh:acme:2"]  # Haifa is reported, not shown


def test_bad_token_goes_to_errors_not_exception(store):
    out = T.search_jobs(store, roles=["backend"], cities=["Tel Aviv"])
    assert out["errors"] and out["errors"][0]["company"] == "BadCo"


def test_no_description_in_search_and_lever_stripped(store):
    out = T.search_jobs(store, roles=["backend"], cities=["Tel Aviv"])
    text = T.compact_json(out)
    assert "LONG" not in text and "description" not in text
    assert set(out["jobs"][0]) <= {"id", "t", "co", "city", "url", "remote"}


def test_only_new_skips_seen_and_outside_not_marked_seen(store):
    first = T.search_jobs(store, roles=["backend"], cities=["Tel Aviv"])
    assert "gh:acme:2" not in store.seen()  # outside_cities jobs are not marked seen
    second = T.search_jobs(store, roles=["backend"], cities=["Tel Aviv"], only_new=True)
    assert second["jobs"] == [] and second["n_skipped_seen"] == len(first["jobs"])


def test_profile_defaults_used(store):
    T.update_profile(store, "test", roles=["backend"], cities=["tel aviv"], strict_cities=True)
    assert store.profile()["cities"] == ["Tel Aviv"]
    assert "gh:acme:2" not in ids(T.search_jobs(store))


def test_track_and_status_history(store):
    T.search_jobs(store, roles=["backend"], cities=["Tel Aviv"])
    T.track_job(store, "gh:acme:1", "saved")
    out = T.track_job(store, "gh:acme:1", "applied", note="via site")
    job = store.tracker()["jobs"]["gh:acme:1"]
    assert [h["status"] for h in job["history"]] == ["saved", "applied"] and "warning" not in out
    assert "unusual" in T.track_job(store, "gh:acme:1", "saved")["warning"]  # allowed, with a warning
    assert T.get_tracker(store, "applied")["n"] == 0  # now saved again


def test_track_unknown_job_is_error(store):
    with pytest.raises(ValueError, match="Call search_jobs first"):
        T.track_job(store, "gh:x:1", "saved")


def test_profile_changes_logged(store):
    T.update_profile(store, "user: only TLV", cities=["Tel Aviv"], strict_cities=True)
    ch = store.profile()["changes"]
    assert {c["field"] for c in ch} == {"cities", "strict_cities"} and ch[0]["reason"] == "user: only TLV"
    T.update_profile(store, "same again", cities=["Tel Aviv"])  # no-op logs nothing
    assert len(store.profile()["changes"]) == 2


def test_get_job_details_cleans_html(store):
    out = T.get_job_details(store, "gh:acme:1")
    assert "Python" in out["description"] and "We are great" not in out["description"]
    assert len(out["description"]) <= 1503


def test_manage_companies(store):
    assert len(T.manage_companies(store, "list")["companies"]) == 3
    with pytest.raises(Exception):
        T.manage_companies(store, "add", "Ghost", "greenhouse", "ghost")  # token validation fails
    assert T.manage_companies(store, "remove", "BadCo")["ok"]


def test_run_tool_logs_and_wraps_errors(store):
    ok = T.run_tool(store, "get_tracker", {})
    bad = T.run_tool(store, "track_job", {"job_id": "gh:x:1", "status": "saved"})
    unk = T.run_tool(store, "nope", {})
    arg = T.run_tool(store, "get_tracker", {"bogus": 1})
    assert ok["ok"] and not bad["ok"] and not unk["ok"] and not arg["ok"]
    log = store.read_jsonl("tool_log.jsonl")
    assert [e["ok"] for e in log] == [True, False, False, False] and log[0]["turn"] == "t1"
    json.loads(ok["text"])
