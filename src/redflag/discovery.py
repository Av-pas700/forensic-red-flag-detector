"""Systematic case discovery from the SEC's Accounting and Auditing Enforcement Releases (AAER) list.

The first 14 cases were chosen from memory of famous failures (hindsight, fame bias). This module
removes the memory step: it scrapes SEC's public AAER index, keeps releases whose first respondent
is a company, resolves each name to an EDGAR CIK, and keeps those with an Item 4.02 8-K. Every
inclusion rule is mechanical and fixed in ``docs/case_selection.md`` *before* outcomes are scored.
"""

from __future__ import annotations

import html
import re

import pandas as pd

from .edgar import EdgarClient

AAER_URL = "https://www.sec.gov/enforcement-litigation/accounting-auditing-enforcement-releases"
ROW = re.compile(
    r'<time datetime="(?P<date>[\d-]+)T[^"]*"[^>]*>.*?'
    r"<div class='release-view__respondents'><a href='(?P<href>[^']+)'>(?P<names>.*?)</a></div>.*?"
    r'view-table_subfield_value">(?P<rel>[^<]*)</span>',
    re.S,
)
CORP = re.compile(
    r"\b(Inc\.?|Corp\.?|Corporation|Company|Co\.|Ltd\.?|Limited|LLC|L\.P\.|plc|PLC|Holdings?|Group|"
    r"Technologies|Systems|Industries|International|N\.V\.|S\.A\.|SE|AG)\b"
)
NOT_COMPANY = re.compile(
    r"\bCPA\b|LLP\b|\bP\.C\.?\b|Chartered|Accountants|Auditors|Partners\b|\bet al\.", re.I
)
STOP = re.compile(r"[^a-z0-9 ]")
SUFFIXES = {
    "inc",
    "corp",
    "corporation",
    "co",
    "company",
    "ltd",
    "limited",
    "llc",
    "lp",
    "plc",
    "holdings",
    "holding",
    "group",
    "the",
    "incorporated",
    "sa",
    "nv",
    "ag",
    "se",
}


def scrape_aaer(client: EdgarClient, max_pages: int = 34) -> pd.DataFrame:
    rows = []
    for page in range(max_pages):
        text = client.get_text(f"{AAER_URL}?page={page}", f"aaer/page_{page}.html")
        for m in ROW.finditer(text):
            rel = html.unescape(m.group("rel")).strip()
            aaer = re.search(r"AAER-(\d+)", rel)
            rows.append(
                {
                    "aaer_no": int(aaer.group(1)) if aaer else None,
                    "aaer_date": pd.Timestamp(m.group("date")),
                    "respondents": html.unescape(re.sub(r"<[^>]+>", "", m.group("names"))).strip(),
                    "release_no": rel,
                    "url": m.group("href")
                    if m.group("href").startswith("http")
                    else "https://www.sec.gov" + m.group("href"),
                }
            )
    df = pd.DataFrame(rows).drop_duplicates(["aaer_no", "respondents"])
    return df.sort_values("aaer_date").reset_index(drop=True)


def company_name(respondents: str) -> str | None:
    """First respondent if it looks like a company (not an individual, auditor or CPA)."""
    first = (
        respondents.split(", ")[0]
        if " and " not in respondents.split(", ")[0]
        else respondents.split(" and ")[0]
    )
    first = re.sub(r"\s*\(.*?\)\s*$", "", first).strip()
    if NOT_COMPANY.search(first) or not CORP.search(first):
        return None
    return first


def norm(name: str) -> str:
    toks = [t for t in STOP.sub(" ", name.lower()).split() if t not in SUFFIXES]
    return " ".join(toks)


def resolve_cik(client: EdgarClient, name: str) -> list[tuple[int, str]]:
    """EDGAR CIKs whose display name (current or former) equals ``name`` after normalisation."""
    key = "disc_" + re.sub(r"[^A-Za-z0-9]", "", name)[:60]
    data = client.full_text_search(f'"{name}"', key, forms="8-K,10-K")
    want = norm(name)
    found: dict[int, str] = {}
    for h in data["hits"]["hits"]:
        s = h["_source"]
        for cik, disp in zip(s["ciks"], s["display_names"], strict=False):
            base = re.sub(r"\s*\(.*$", "", disp)
            if norm(base) == want:
                found[int(cik)] = base
    return sorted(found.items())


def item_402_section(text: str, n: int = 5000) -> str:
    ms = list(re.finditer(r"item\s*4\.02\.?\s*(\(a\))?\s*non-reliance", text, re.I))
    i = ms[-1].start() if ms else max(text.lower().find("item 4.02"), 0)
    sec = text[i : i + n]
    end = re.search(r"\bItem\s+(5\.|7\.|8\.|9\.)|SIGNATURE", sec[200:], re.I)
    return sec[: 200 + end.start()] if end else sec


def years_in_year_sentences(section: str) -> list[int]:
    """Years mentioned in sentences about fiscal/annual periods (a hint only; reviewed by hand)."""
    years: set[int] = set()
    for sent in re.split(r"(?<=[.;])\s+", section):
        if re.search(r"fiscal|year|annual|10-K", sent, re.I) and not re.search(
            r"\bfiled\b|dated|previously (filed|disclosed)", sent, re.I
        ):
            years |= {int(y) for y in re.findall(r"\b(20[0-2]\d)\b", sent)}
    return sorted(years)
