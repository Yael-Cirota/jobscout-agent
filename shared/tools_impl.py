"""The 7 JobScout tools as plain Python functions: (store, **args) -> dict, or raise."""
import json

from . import boards, locations, roles as roles_mod, store as store_mod

STATUS_RANK = {"saved": 0, "applied": 1, "interview": 2, "offer": 3, "rejected": 3}
MAX_OUTSIDE = 3


def compact_json(obj):
    return json.dumps(obj, separators=(",", ":"), ensure_ascii=False)


def _row(job):
    row = {"id": job["id"], "t": job["title"], "co": job["company"], "city": job["city"]}
    return row


def _find_company(store, token, ats):
    for c in store.companies():
        if c["token"] == token and c["ats"] == ats:
            return c
    raise ValueError(f"Company {token!r} ({ats}) is not in the company list.")


def search_jobs(store, roles=None, cities=None, only_new=False, limit=10):
    profile = store.profile()
    roles = roles or profile["roles"]
    explicit = bool(cities)
    wanted = [locations.canonical_city(c) or c for c in (cities or profile["cities"])]
    limit = max(1, min(int(limit or 10), 20))
    skip = {s.lower() for s in profile["skip_companies"]}
    seen = store.seen()

    matches, errors = [], []
    for comp in store.companies():
        if comp["name"].lower() in skip:
            continue
        try:
            jobs = boards.list_jobs(store.http, comp)
        except Exception as e:
            errors.append({"company": comp["name"], "error": str(e)})
            continue
        matches += [j for j in jobs
                    if locations.is_israel(j["location"]) and roles_mod.matches_roles(j["title"], roles)]

    inside = [j for j in matches if not wanted or j["city"] in wanted]
    outside = [j for j in matches if wanted and j["city"] not in wanted]
    fresh = [j for j in inside if not (only_new and j["id"] in seen)]
    shown = fresh[:limit]
    outside = [j for j in outside if not (only_new and j["id"] in seen)][:MAX_OUTSIDE]

    store.mark_seen([j["id"] for j in shown])
    store.remember_jobs([{**_row(j), "url": j["url"]} for j in shown + outside])

    rows = []
    for j in shown:
        r = {**_row(j), "url": j["url"]}
        if j["remote"]:
            r["remote"] = True
        rows.append(r)
    out = {"jobs": rows, "n_total_matches": len(inside), "n_shown": len(shown),
           "n_skipped_seen": len(inside) - len(fresh),
           "outside_cities": [_row(j) for j in outside], "errors": errors}
    if explicit and profile["strict_cities"] and set(wanted) - set(profile["cities"]):
        out["profile_conflict"] = "strict_cities is on but the requested cities differ from the profile"
    return out


def get_job_details(store, job_id):
    ats, token, raw = boards.parse_id(job_id)
    comp = _find_company(store, token, ats)
    job, desc = boards.get_description(store.http, comp, raw)
    store.remember_jobs([{**_row(job), "url": job["url"]}])
    return {"id": job["id"], "t": job["title"], "co": job["company"], "city": job["city"],
            "url": job["url"], "description": desc}


def track_job(store, job_id, status, note=""):
    if status not in STATUS_RANK:
        raise ValueError(f"Unknown status {status!r}. Use one of: {', '.join(STATUS_RANK)}.")
    tracker = store.tracker()
    entry = tracker["jobs"].get(job_id)
    if entry is None:
        info = store.known_jobs().get(job_id)
        if info is None:
            raise ValueError(f"Unknown job id {job_id}. Call search_jobs first.")
        entry = {"title": info["t"], "company": info["co"], "city": info["city"],
                 "url": info.get("url", ""), "status": None, "history": [], "notes": ""}
        tracker["jobs"][job_id] = entry
    warning = None
    old = entry["status"]
    if old == status:
        warning = f"already {status}"
    elif old and status != "rejected" and STATUS_RANK[status] < STATUS_RANK[old]:
        warning = f"unusual move {old} -> {status}"
    entry["status"] = status
    entry["history"].append({"status": status, "at": store_mod.now()})
    if note:
        entry["notes"] = (entry["notes"] + "\n" + note).strip()
    store.save_tracker(tracker)
    out = {"ok": True, "id": job_id, "status": status}
    if warning:
        out["warning"] = warning
    return out


def get_tracker(store, status=None):
    jobs = store.tracker()["jobs"]
    lines = [f'{jid} · {j["title"]} · {j["company"]} · {j["status"]} · {j["history"][-1]["at"][:10]}'
             for jid, j in jobs.items() if status in (None, j["status"])]
    return {"n": len(lines), "jobs": lines}


def update_profile(store, reason, roles=None, cities=None, strict_cities=None, skip_companies=None):
    if not (reason or "").strip():
        raise ValueError("A reason is required.")
    profile = store.profile()
    new = {}
    if roles is not None:
        new["roles"] = [roles_mod.normalize_role(r) for r in roles]
    if cities is not None:
        new["cities"] = [locations.canonical_city(c) or c.strip() for c in cities]
    if strict_cities is not None:
        new["strict_cities"] = bool(strict_cities)
    if skip_companies is not None:
        new["skip_companies"] = list(skip_companies)
    changes = []
    for field, value in new.items():
        if profile[field] != value:
            changes.append({"field": field, "old": profile[field], "new": value,
                            "reason": reason, "at": store_mod.now()})
            profile[field] = value
    if changes:
        profile["changes"] += changes
        profile["updated_at"] = store_mod.now()
        store.save_profile(profile)
    return {"ok": True, "changed": [c["field"] for c in changes],
            "profile": {k: profile[k] for k in ("roles", "cities", "strict_cities", "skip_companies")}}


def get_profile(store):
    return store.profile()


def manage_companies(store, action, name=None, ats=None, token=None):
    companies = store.companies()
    if action == "list":
        return {"companies": [f'{c["name"]} ({c["ats"]}:{c["token"]})' for c in companies]}
    if not name:
        raise ValueError("name is required.")
    if action == "remove":
        kept = [c for c in companies if c["name"].lower() != name.lower()]
        if len(kept) == len(companies):
            raise ValueError(f"{name} is not in the company list.")
        store.save_companies(kept)
        return {"ok": True, "removed": name}
    if action == "add":
        if ats not in boards.PREFIX or not token:
            raise ValueError("add needs ats (greenhouse|lever) and token.")
        if any(c["name"].lower() == name.lower() for c in companies):
            raise ValueError(f"{name} is already in the company list.")
        comp = {"name": name, "ats": ats, "token": token}
        n = len(boards.list_jobs(store.http, comp))  # raises on a bad token
        store.save_companies(companies + [comp])
        return {"ok": True, "added": f"{name} ({ats})", "open_jobs": n}
    raise ValueError(f"Unknown action {action!r}. Use list, add or remove.")


TOOL_FUNCS = {f.__name__: f for f in (search_jobs, get_job_details, track_job, get_tracker,
                                      update_profile, get_profile, manage_companies)}


def _has_key(obj, keys):
    if isinstance(obj, dict):
        return any(k in keys for k in obj) or any(_has_key(v, keys) for v in obj.values())
    if isinstance(obj, list):
        return any(_has_key(v, keys) for v in obj)
    return False


def run_tool(store, name, args):
    """Run a tool with logging. Returns {"ok": bool, "text": compact JSON or error message}."""
    args = args or {}
    try:
        if name not in TOOL_FUNCS:
            raise ValueError(f"Unknown tool {name!r}.")
        result = TOOL_FUNCS[name](store, **args)
        text = compact_json(result)
        entry = {"tool": name, "args": args, "ok": True, "chars": len(text)}
        if name == "search_jobs":
            entry["ids"] = [j["id"] for j in result["jobs"]]
            entry["has_description"] = _has_key(result, {"description", "content"})
        store.log_tool(entry)
        return {"ok": True, "text": text}
    except Exception as e:  # tool errors go back to the model, they never crash the loop
        msg = str(e) if isinstance(e, ValueError) else f"{type(e).__name__}: {e}"
        store.log_tool({"tool": name, "args": args, "ok": False, "chars": len(msg), "error": msg})
        return {"ok": False, "text": msg}
