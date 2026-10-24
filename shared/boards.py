"""Greenhouse + Lever clients, normalized to one short Job shape."""
from . import locations, text

GH_LIST = "https://boards-api.greenhouse.io/v1/boards/{token}/jobs"
GH_ONE = "https://boards-api.greenhouse.io/v1/boards/{token}/jobs/{id}"
LV_LIST = "https://api.lever.co/v0/postings/{token}?mode=json"
LV_ONE = "https://api.lever.co/v0/postings/{token}/{id}"
PREFIX = {"greenhouse": "gh", "lever": "lv"}
ATS_OF = {v: k for k, v in PREFIX.items()}


def make_id(ats, token, raw_id):
    return f"{PREFIX[ats]}:{token}:{raw_id}"


def parse_id(job_id):
    try:
        prefix, token, raw = job_id.split(":", 2)
        return ATS_OF[prefix], token, raw
    except (ValueError, KeyError):
        raise ValueError(f"Bad job id {job_id!r}. Expected gh:<token>:<id> or lv:<token>:<id>.")


def _job(company, ats, raw_id, title, location, url):
    return {
        "id": make_id(ats, company["token"], raw_id),
        "title": (title or "").strip(),
        "company": company["name"],
        "location": location or "",
        "city": locations.city_of(location),
        "remote": locations.is_remote(location),
        "url": url,
    }


def list_jobs(http, company):
    """Short job rows for one company. Never includes descriptions."""
    ats, token = company["ats"], company["token"]
    if ats == "greenhouse":
        data = http.fetch_json(GH_LIST.format(token=token))
        return [_job(company, ats, j["id"], j.get("title"), (j.get("location") or {}).get("name"),
                     j.get("absolute_url")) for j in data.get("jobs", [])]
    if ats == "lever":
        data = http.fetch_json(LV_LIST.format(token=token))
        # Lever's list already carries long descriptions: they are dropped here.
        return [_job(company, ats, j["id"], j.get("text"), (j.get("categories") or {}).get("location"),
                     j.get("hostedUrl")) for j in data]
    raise ValueError(f"Unknown ats {ats!r}")


def get_description(http, company, raw_id):
    """Cleaned, truncated plain-text description of one job."""
    ats, token = company["ats"], company["token"]
    if ats == "greenhouse":
        data = http.fetch_json(GH_ONE.format(token=token, id=raw_id))
        body = text.html_to_text(data.get("content", ""), escaped=True)
        job = _job(company, ats, raw_id, data.get("title"), (data.get("location") or {}).get("name"),
                   data.get("absolute_url"))
    else:
        data = http.fetch_json(LV_ONE.format(token=token, id=raw_id))
        parts = [data.get("descriptionPlain") or text.html_to_text(data.get("description", ""))]
        for lst in data.get("lists", []):
            parts.append(f"{lst.get('text', '')}\n{text.html_to_text(lst.get('content', ''))}")
        parts.append(data.get("additionalPlain") or "")
        body = "\n\n".join(p for p in parts if p)
        job = _job(company, ats, raw_id, data.get("text"), (data.get("categories") or {}).get("location"),
                   data.get("hostedUrl"))
    return job, text.clean_description(body)
