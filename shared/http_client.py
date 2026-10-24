"""fetch_json with timeout, retry, logging, in-run cache and record/replay.

JOBSCOUT_HTTP=live (default) | record | replay
"""
import hashlib
import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

FIXTURES = Path(__file__).parent / "fixtures"


class HttpError(Exception):
    pass


def fixture_path(url):
    return FIXTURES / (hashlib.sha1(url.encode()).hexdigest()[:16] + ".json")


class HttpClient:
    def __init__(self, log_path=None, mode=None, turn_getter=None, timeout=20):
        self.mode = mode or os.environ.get("JOBSCOUT_HTTP", "live")
        self.log_path = Path(log_path) if log_path else None
        self.turn_getter = turn_getter or (lambda: None)
        self.timeout = timeout
        self.cache = {}

    def _log(self, url, status, source, ms):
        if not self.log_path:
            return
        entry = {"ts": time.time(), "turn": self.turn_getter(), "url": url,
                 "status": status, "source": source, "ms": ms, "mode": self.mode}
        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")

    def fetch_json(self, url):
        if url in self.cache:
            self._log(url, 200, "cache", 0)
            return self.cache[url]
        t0 = time.time()
        if self.mode == "replay":
            fp = fixture_path(url)
            if not fp.exists():
                self._log(url, 404, "replay", 0)
                raise HttpError(f"HTTP 404 - no fixture for {url}")
            data = json.loads(fp.read_text(encoding="utf-8"))["data"]
            source = "replay"
        else:
            data = self._live(url)
            source = "live"
            if self.mode == "record":
                FIXTURES.mkdir(exist_ok=True)
                fixture_path(url).write_text(
                    json.dumps({"url": url, "data": data}, ensure_ascii=False), encoding="utf-8")
        self._log(url, 200, source, int((time.time() - t0) * 1000))
        self.cache[url] = data
        return data

    def _live(self, url):
        last = None
        for attempt in range(3):
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "jobscout/1.0"})
                with urllib.request.urlopen(req, timeout=self.timeout) as r:
                    return json.loads(r.read().decode("utf-8"))
            except urllib.error.HTTPError as e:
                last = e
                self._log(url, e.code, "live", 0)
                if e.code < 500:
                    raise HttpError(f"HTTP {e.code} - check board token") from e
            except (urllib.error.URLError, TimeoutError) as e:
                last = e
            time.sleep(0.5 * (attempt + 1))
        raise HttpError(f"request failed: {last}")
