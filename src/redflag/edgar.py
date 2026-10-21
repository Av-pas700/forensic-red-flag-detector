"""SEC EDGAR client: polite, cached access to XBRL ``companyfacts`` and ``submissions``.

All raw responses are cached under ``data/raw`` so that analysis is reproducible and the
SEC is not hit twice for the same document.
"""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path

import requests

from . import config

FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json"
SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik:010d}.json"
SUBMISSIONS_PAGE_URL = "https://data.sec.gov/submissions/{name}"
FTS_URL = "https://efts.sec.gov/LATEST/search-index"
ARCHIVES_URL = "https://www.sec.gov/Archives/edgar/data/{cik}/{acc_nodash}/{doc}"
INDEX_URL = "https://www.sec.gov/Archives/edgar/data/{cik}/{acc_nodash}/"


class RateLimiter:
    """Thread-safe minimum-interval limiter (requests per second ceiling)."""

    def __init__(self, per_second: float) -> None:
        self._interval = 1.0 / per_second
        self._lock = threading.Lock()
        self._last = 0.0

    def wait(self) -> None:
        with self._lock:
            now = time.monotonic()
            delay = self._last + self._interval - now
            if delay > 0:
                time.sleep(delay)
            self._last = time.monotonic()


class EdgarClient:
    """Minimal EDGAR client with on-disk JSON caching and a hard rate limit."""

    def __init__(self, cache_dir: Path | None = None, user_agent: str | None = None) -> None:
        self.cache_dir = Path(cache_dir) if cache_dir else config.DATA_RAW
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._ua = user_agent
        self._limiter = RateLimiter(config.MAX_REQUESTS_PER_SECOND)
        self._session: requests.Session | None = None

    @property
    def session(self) -> requests.Session:
        if self._session is None:
            ua = self._ua or config.get_user_agent()
            self._session = requests.Session()
            self._session.headers.update({"User-Agent": ua, "Accept-Encoding": "gzip, deflate"})
        return self._session

    def _get(self, url: str, params: dict | None = None, retries: int = 4) -> requests.Response:
        for attempt in range(retries):
            self._limiter.wait()
            resp = self.session.get(url, params=params, timeout=60)
            if resp.status_code in (429, 503):
                time.sleep(2**attempt)
                continue
            resp.raise_for_status()
            return resp
        resp.raise_for_status()
        return resp

    def get_json(self, url: str, cache_name: str, params: dict | None = None) -> dict:
        path = self.cache_dir / cache_name
        if path.is_file():
            return json.loads(path.read_text())
        data = self._get(url, params=params).json()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data))
        return data

    def get_text(self, url: str, cache_name: str) -> str:
        path = self.cache_dir / cache_name
        if path.is_file():
            return path.read_text(errors="replace")
        text = self._get(url).text
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        return text

    # ------------------------------------------------------------------ endpoints
    def company_facts(self, cik: int) -> dict:
        return self.get_json(FACTS_URL.format(cik=cik), f"facts/CIK{cik:010d}.json")

    def submissions(self, cik: int) -> dict:
        return self.get_json(SUBMISSIONS_URL.format(cik=cik), f"submissions/CIK{cik:010d}.json")

    def all_filings(self, cik: int) -> list[dict]:
        """Return every filing as a list of row dicts, including the older paged files."""
        sub = self.submissions(cik)
        frames = [sub["filings"]["recent"]]
        for extra in sub["filings"].get("files", []):
            name = extra["name"]
            frames.append(self.get_json(SUBMISSIONS_PAGE_URL.format(name=name), f"submissions/{name}"))
        rows: list[dict] = []
        for frame in frames:
            keys = list(frame)
            n = len(frame["accessionNumber"])
            rows.extend({k: frame[k][i] for k in keys} for i in range(n))
        return rows

    def items_402(self, cik: int) -> list[dict]:
        """8-K filings that carry Item 4.02 (non-reliance on previously issued financials)."""
        out = []
        for row in self.all_filings(cik):
            items = [i.strip() for i in str(row.get("items", "")).split(",")]
            if row.get("form", "").startswith("8-K") and "4.02" in items:
                out.append(row)
        return sorted(out, key=lambda r: r["filingDate"])

    def full_text_search(self, query: str, cache_name: str, **params) -> dict:
        params = {"q": query, **params}
        return self.get_json(FTS_URL, f"fts/{cache_name}.json", params=params)

    def frame(self, tag: str, unit: str, period: str) -> list[dict]:
        """XBRL ``frames`` API: one value per company for a tag and calendar period."""
        url = f"https://data.sec.gov/api/xbrl/frames/us-gaap/{tag}/{unit}/{period}.json"
        return self.get_json(url, f"frames/{tag}_{unit}_{period}.json").get("data", [])
