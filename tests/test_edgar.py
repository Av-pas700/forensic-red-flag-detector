"""Ingestion: credentials come from the environment only, requests are throttled and cached."""

import time

import pandas as pd
import pytest

from redflag import config
from redflag.cases import verify_cases
from redflag.controls import frame_period, sic_division
from redflag.edgar import EdgarClient, RateLimiter


def test_user_agent_is_required_and_read_from_env(monkeypatch, tmp_path):
    monkeypatch.delenv("SEC_USER_AGENT", raising=False)
    monkeypatch.setattr(config, "ROOT", tmp_path)  # no .env here either
    with pytest.raises(RuntimeError, match="SEC_USER_AGENT"):
        config.get_user_agent()
    monkeypatch.setenv("SEC_USER_AGENT", "Test Person test@example.com")
    assert config.get_user_agent() == "Test Person test@example.com"


def test_user_agent_falls_back_to_gitignored_dotenv(monkeypatch, tmp_path):
    monkeypatch.delenv("SEC_USER_AGENT", raising=False)
    (tmp_path / ".env").write_text('# comment\nSEC_USER_AGENT="Dot Env dot@example.com"\n')
    monkeypatch.setattr(config, "ROOT", tmp_path)
    assert config.get_user_agent() == "Dot Env dot@example.com"


def test_dotenv_is_gitignored():
    ignore = (config.ROOT / ".gitignore").read_text().splitlines()
    assert ".env" in ignore and "data/raw/" in ignore


def test_rate_limiter_enforces_minimum_interval():
    rl = RateLimiter(per_second=20)
    start = time.monotonic()
    for _ in range(5):
        rl.wait()
    assert time.monotonic() - start >= 4 / 20 - 0.01


def test_configured_rate_is_below_the_sec_limit():
    assert config.MAX_REQUESTS_PER_SECOND < 10


def test_get_json_caches_to_disk_and_hits_network_once(tmp_path, monkeypatch):
    client = EdgarClient(cache_dir=tmp_path, user_agent="x y@z.com")
    calls = []

    class Resp:
        def json(self):
            return {"ok": 1}

    monkeypatch.setattr(client, "_get", lambda url, params=None, retries=4: calls.append(url) or Resp())
    assert client.get_json("https://data.sec.gov/x", "a/b.json") == {"ok": 1}
    assert client.get_json("https://data.sec.gov/x", "a/b.json") == {"ok": 1}
    assert len(calls) == 1 and (tmp_path / "a" / "b.json").exists()


def test_frame_period_picks_nearest_quarter_end():
    assert frame_period(pd.Timestamp("2012-01-28")) == "CY2011Q4I"
    assert frame_period(pd.Timestamp("2013-06-30")) == "CY2013Q2I"
    assert frame_period(pd.Timestamp("2014-09-27")) == "CY2014Q3I"


def test_sic_division_and_financial_exclusion():
    from redflag.controls import FINANCIAL_SIC

    assert sic_division(2834) == sic_division(3841)
    assert 6199 in FINANCIAL_SIC and 6798 in FINANCIAL_SIC and 7372 not in FINANCIAL_SIC


class _FakeClient:
    def __init__(self, rows):
        self._rows = rows

    def all_filings(self, cik):
        return self._rows


def _case(**kw):
    base = {
        "case_id": "c",
        "cik": 1,
        "nonreliance_accn": "A-1",
        "nonreliance_date": pd.Timestamp("2015-06-01"),
        "first_signal_accn": "",
        "first_signal_date": pd.NaT,
    }
    return pd.DataFrame([{**base, **kw}])


def test_verify_cases_rejects_a_citation_that_is_not_a_4_02(monkeypatch):
    rows = [
        {
            "accessionNumber": "A-1",
            "form": "8-K",
            "items": "2.02,9.01",
            "filingDate": "2015-06-01",
            "primaryDocument": "x.htm",
        }
    ]
    with pytest.raises(ValueError, match="not a 4.02"):
        verify_cases(_FakeClient(rows), _case())


def test_verify_cases_rejects_wrong_date_and_unknown_accession():
    rows = [
        {
            "accessionNumber": "A-1",
            "form": "8-K",
            "items": "4.02",
            "filingDate": "2015-06-02",
            "primaryDocument": "x.htm",
        }
    ]
    with pytest.raises(ValueError, match="not a 4.02"):
        verify_cases(_FakeClient(rows), _case())
    with pytest.raises(ValueError, match="not found"):
        verify_cases(_FakeClient([]), _case())


def test_verify_cases_accepts_good_citation_and_finds_bankruptcy():
    rows = [
        {
            "accessionNumber": "A-1",
            "form": "8-K",
            "items": "4.02,9.01",
            "filingDate": "2015-06-01",
            "primaryDocument": "x.htm",
        },
        {
            "accessionNumber": "B-1",
            "form": "8-K",
            "items": "1.03",
            "filingDate": "2016-01-10",
            "primaryDocument": "y.htm",
        },
    ]
    out = verify_cases(_FakeClient(rows), _case()).iloc[0]
    assert out["nonreliance_url"].endswith("/x.htm") and out["bankruptcy_date"] == pd.Timestamp("2016-01-10")
