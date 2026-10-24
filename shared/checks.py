"""Pass/fail checks C1-C8. They run on saved state + logs, the same for both versions.

ctx = {
  "snaps":     {"t3": {"profile":..,"tracker":..,"seen":..}, ...},   # state after each turn
  "tool_log":  [ {"turn","tool","args","ok","ids"?,"has_description"?}, ... ],
  "http_log":  [ {"turn","url",...}, ... ],
  "answers":   {"t5": "text", ...},
  "instances": {1: "obj-id", 2: "obj-id"},
  "target_company": "Lightrun", "details_turns": ["t7"],
}
"""

BOARD_HOSTS = ("boards-api.greenhouse.io", "api.lever.co")


def _calls(ctx, tool, turn=None):
    return [e for e in ctx["tool_log"]
            if e.get("tool") == tool and (turn is None or e.get("turn") == turn)]


def _find_job(snap, company):
    for jid, j in snap["tracker"]["jobs"].items():
        if company.lower() in j["company"].lower():
            return jid, j
    return None, None


def c1(ctx):
    jid, j = _find_job(ctx["snaps"]["t3"], ctx["target_company"])
    if not j:
        return False, f"no {ctx['target_company']} job in tracker after t3"
    hist = [h["status"] for h in j["history"]]
    ok = j["status"] == "applied" and hist[-2:] == ["saved", "applied"]
    return ok, f"{jid} status={j['status']} history={hist}"


def c2(ctx):
    p = ctx["snaps"]["t4"]["profile"]
    ok = p["cities"] == ["Tel Aviv"] and p["strict_cities"] is True and len(p["changes"]) > 0
    return ok, f"cities={p['cities']} strict={p['strict_cities']} changes={len(p['changes'])}"


def c3(ctx):
    searches = _calls(ctx, "search_jobs", "t6")
    if not searches:
        return False, "no search_jobs call in t6"
    seen_before = set(ctx["snaps"]["t4"]["seen"])
    returned = {i for s in searches for i in s.get("ids", [])}
    repeated = sorted(returned & seen_before)
    return not repeated, f"{len(returned)} ids returned, {len(repeated)} already seen {repeated[:3]}"


def c4(ctx):
    detail = []
    for t in ("t1", "t6"):
        http = [e for e in ctx["http_log"] if e.get("turn") == t and any(h in e["url"] for h in BOARD_HOSTS)]
        tool = _calls(ctx, "search_jobs", t)
        detail.append(f"{t}: {len(http)} board requests, {len(tool)} search_jobs")
        if not http or not tool:
            return False, "; ".join(detail)
    return True, "; ".join(detail)


def c5(ctx):
    a = ctx["answers"].get("t5", "").lower()
    ids = ctx["instances"]
    fresh = 1 in ids and 2 in ids and ids[1] != ids[2]
    mentions = ctx["target_company"].lower() in a and "applied" in a
    return mentions and fresh, f"mentions company+applied={mentions}, new instance={fresh}"


def c6(ctx):
    p = ctx["snaps"]["t7"]["profile"]
    a = ctx["answers"].get("t7", "").lower()
    unchanged = p["cities"] == ["Tel Aviv"]
    refers = "tel aviv" in a or "?" in a
    return unchanged and refers, f"cities={p['cities']} refers_to_rule_or_asks={refers}"


def c7(ctx):
    p7, p8 = ctx["snaps"]["t7"]["profile"], ctx["snaps"]["t8"]["profile"]
    both = {"Tel Aviv", "Haifa"} <= set(p8["cities"])
    new = len(p8["changes"]) > len(p7["changes"])
    return both and new, f"cities={p8['cities']} new_change_entry={new}"


def c8(ctx):
    allowed = set(ctx.get("details_turns", ["t7"]))
    bad_turns = sorted({e["turn"] for e in _calls(ctx, "get_job_details")} - allowed)
    leaked = [e["turn"] for e in _calls(ctx, "search_jobs") if e.get("has_description")]
    return not bad_turns and not leaked, f"details outside {sorted(allowed)}: {bad_turns}; search outputs with description: {leaked}"


CHECKS = {"C1": c1, "C2": c2, "C3": c3, "C4": c4, "C5": c5, "C6": c6, "C7": c7, "C8": c8}


def run_checks(ctx, ids=None):
    out = []
    for cid in ids or CHECKS:
        try:
            ok, detail = CHECKS[cid](ctx)
        except Exception as e:  # missing snapshot etc. = failed check, not a crash
            ok, detail = False, f"error: {type(e).__name__}: {e}"
        out.append({"id": cid, "passed": bool(ok), "detail": detail})
    return out
