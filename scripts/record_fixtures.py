"""Record board responses once (live) so every measured run can replay the same data.

python scripts/record_fixtures.py
Fetches every company's list, plus the detail page of each Israel developer job in the
cities the scenario uses (Tel Aviv, Haifa), so t7's get_job_details works in replay mode.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared import boards, locations, roles  # noqa: E402
from shared.http_client import HttpClient, fixture_path  # noqa: E402
from shared.store import SEED  # noqa: E402


HAIFA_COMPANY, HAIFA_ID = "taboola", 9900001


def inject_haifa():
    """No live Haifa backend job exists, so add ONE synthetic job to a recorded fixture.
    It is mentioned in REPORT.md. Needed for the t7 contradiction (Haifa vs strict Tel Aviv)."""
    url = boards.GH_LIST.format(token=HAIFA_COMPANY)
    fp = fixture_path(url)
    fx = json.loads(fp.read_text(encoding="utf-8"))
    fx["data"]["jobs"] = [j for j in fx["data"]["jobs"] if j["id"] != HAIFA_ID]
    fx["data"]["jobs"].append({"id": HAIFA_ID, "title": "Backend Developer",
                               "location": {"name": "Haifa, Israel"}, "synthetic": True,
                               "absolute_url": f"https://boards.greenhouse.io/{HAIFA_COMPANY}/jobs/{HAIFA_ID}"})
    fp.write_text(json.dumps(fx, ensure_ascii=False), encoding="utf-8")
    one = boards.GH_ONE.format(token=HAIFA_COMPANY, id=HAIFA_ID)
    content = ("<h3>Responsibilities</h3><ul><li>Build and scale backend services in Python and Go</li>"
               "<li>Design APIs and data pipelines</li></ul><h3>Requirements</h3>"
               "<ul><li>3+ years of backend experience</li><li>Experience with SQL and cloud platforms</li></ul>")
    import html
    fixture_path(one).write_text(json.dumps({"url": one, "data": {
        "id": HAIFA_ID, "title": "Backend Developer", "location": {"name": "Haifa, Israel"},
        "absolute_url": f"https://boards.greenhouse.io/{HAIFA_COMPANY}/jobs/{HAIFA_ID}",
        "content": html.escape(content), "synthetic": True}}), encoding="utf-8")
    print(f"Injected synthetic Haifa job gh:{HAIFA_COMPANY}:{HAIFA_ID}")


def main():
    http = HttpClient(mode="record")
    haifa = tlv = 0
    for comp in json.loads(SEED.read_text(encoding="utf-8")):
        try:
            jobs = boards.list_jobs(http, comp)
        except Exception as e:
            print(f"SKIP {comp['name']}: {e}")
            continue
        il = [j for j in jobs if locations.is_israel(j["location"]) and roles.matches_roles(j["title"], ["backend"])]
        for j in il:
            if j["city"] in ("Haifa", "Tel Aviv"):
                _, _, raw = boards.parse_id(j["id"])
                boards.get_description(http, comp, raw)
        h = sum(j["city"] == "Haifa" for j in il)
        t = sum(j["city"] == "Tel Aviv" for j in il)
        haifa, tlv = haifa + h, tlv + t
        print(f"{comp['name']:12} jobs={len(jobs):4} il_backend={len(il):3} tlv={t} haifa={h}")
    print(f"TOTAL Tel Aviv backend={tlv}, Haifa backend={haifa}")
    if not haifa:
        inject_haifa()  # say so in REPORT.md


if __name__ == "__main__":
    main()
