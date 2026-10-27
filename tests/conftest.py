import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared.store import Store  # noqa: E402


class FakeHttp:
    """Serves canned board JSON by URL; unknown URLs behave like a 404."""

    def __init__(self, routes):
        self.routes, self.calls = routes, []

    def fetch_json(self, url):
        self.calls.append(url)
        if url not in self.routes:
            from shared.http_client import HttpError
            raise HttpError("HTTP 404 - check board token")
        return self.routes[url]


GH = "https://boards-api.greenhouse.io/v1/boards/{}/jobs"
LV = "https://api.lever.co/v0/postings/{}?mode=json"


def gh_job(i, title, loc):
    return {"id": i, "title": title, "location": {"name": loc}, "absolute_url": f"https://x/{i}"}


ROUTES = {
    GH.format("acme"): {"jobs": [
        gh_job(1, "Backend Engineer", "Tel Aviv, Israel"),
        gh_job(2, "Backend Developer", "Haifa, Israel"),
        gh_job(3, "Senior Backend Engineer", "Tel Aviv-Yafo"),
        gh_job(4, "Sales Manager", "Tel Aviv, Israel"),
        gh_job(5, "Backend Engineer", "New York, NY"),
        gh_job(6, "Frontend Engineer", "Tel Aviv, Israel"),
    ]},
    LV.format("lvco"): [
        {"id": "ab12", "text": "Backend Engineer", "hostedUrl": "https://l/ab12",
         "categories": {"location": "Tel Aviv"}, "descriptionPlain": "LONG " * 500},
    ],
    "https://boards-api.greenhouse.io/v1/boards/acme/jobs/1": {
        "id": 1, "title": "Backend Engineer", "location": {"name": "Tel Aviv, Israel"},
        "absolute_url": "https://x/1",
        "content": "&lt;p&gt;About us&lt;/p&gt;&lt;p&gt;We are great.&lt;/p&gt;"
                   "&lt;h3&gt;Requirements&lt;/h3&gt;&lt;ul&gt;&lt;li&gt;Python&lt;/li&gt;&lt;/ul&gt;"},
}
COMPANIES = [{"name": "Acme", "ats": "greenhouse", "token": "acme"},
             {"name": "LvCo", "ats": "lever", "token": "lvco"},
             {"name": "BadCo", "ats": "greenhouse", "token": "nope"}]


@pytest.fixture
def store(tmp_path):
    s = Store(tmp_path / "state", http=FakeHttp(ROUTES))
    s._write("companies.json", COMPANIES)
    s.set_turn(1, "t1")
    return s


@pytest.fixture(autouse=True)
def restore_log_sink():
    from API.harness import logger
    previous = logger._sink
    yield
    logger._sink = previous
