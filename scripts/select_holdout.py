"""Apply the pre-registered mechanical rules (docs/preregistration.md) to data/cases/candidates.csv.

For each (AAER, Item 4.02) pair: positive fiscal years = years named in BOTH the 4.02 text and the AAER
document that also have a usable ORIGINAL 10-K filed before the 4.02 date. A company is kept if any of its
4.02s yields at least one such year; among its 4.02s the one with most overlapping years (then earliest) is used.
Writes data/cases/holdout_selected.csv. Needs SEC_USER_AGENT.
"""

from __future__ import annotations

import html
import io
import re

import pandas as pd

from redflag import config
from redflag.controls import usable_years
from redflag.edgar import EdgarClient
from redflag.statements import extract_annual_statements

_cases = pd.read_csv(config.DATA_CASES / "cases.csv")
DEV = _cases.loc[_cases.get("cohort", "development") == "development", "cik"].tolist()


def aaer_years(client: EdgarClient, url: str) -> set[int]:
    name = "aaer_docs/" + re.sub(r"[^A-Za-z0-9]", "_", url)[-90:]
    try:
        if url.lower().endswith(".pdf"):
            path = client.cache_dir / (name + ".txt")
            if path.is_file():
                text = path.read_text()
            else:
                from pypdf import PdfReader

                resp = client._get(url)
                text = " ".join(
                    (p.extract_text() or "") for p in PdfReader(io.BytesIO(resp.content)).pages[:6]
                )
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(text)
        else:
            raw = client.get_text(url, name + ".html")
            text = html.unescape(
                re.sub(r"<[^>]+>", " ", re.sub(r"<(script|style).*?</\1>", " ", raw, flags=re.S))
            )
    except Exception:
        return set()
    text = re.sub(r"\s+", " ", text)[:20000]
    years: set[int] = set()
    for sent in re.split(r"(?<=[.;])\s+", text):
        if re.search(r"fiscal|year|annual|10-K|restate", sent, re.I):
            years |= {int(y) for y in re.findall(r"\b(20[0-2]\d)\b", sent)}
    return years


def main() -> None:
    client = EdgarClient()
    cand = pd.read_csv(config.DATA_CASES / "candidates.csv")
    cand = cand[~cand["cik"].isin(DEV)]
    cand["years_402"] = (
        cand["years_hint"].fillna("").apply(lambda s: {int(x) for x in str(s).split(";") if x})
    )
    stm_cache: dict[int, pd.DataFrame] = {}
    picks = []
    rejected = []
    for cik, grp in cand.groupby("cik"):
        try:
            stm_cache[cik] = extract_annual_statements(client.company_facts(int(cik)), int(cik))
        except Exception:
            print(f"drop {grp.iloc[0]['edgar_name']:<40} (no XBRL companyfacts)")
            rejected.append(
                {
                    "company": grp.iloc[0]["edgar_name"],
                    "aaer_date": grp.iloc[0]["aaer_date"],
                    "reason": "no XBRL companyfacts on EDGAR",
                }
            )
            continue
        stm = stm_cache[cik]
        if stm.empty:
            print(f"drop {grp.iloc[0]['edgar_name']:<40} (no annual XBRL rows)")
            rejected.append(
                {
                    "company": grp.iloc[0]["edgar_name"],
                    "aaer_date": grp.iloc[0]["aaer_date"],
                    "reason": "no annual XBRL rows",
                }
            )
            continue
        best = None
        for _, r in grp.iterrows():
            ay = aaer_years(client, r["aaer_url"])
            pre = stm[stm["filed"] < pd.Timestamp(r["date_402"])]
            both = sorted((r["years_402"] & ay) & set(pre["fyear"]))
            good = [y for y in both if usable_years(pre, [y])]
            if good and (best is None or (len(good), -pd.Timestamp(r["date_402"]).value) > best[0]):
                best = ((len(good), -pd.Timestamp(r["date_402"]).value), r, good, sorted(ay))
        if best:
            _, r, good, ay = best
            picks.append(
                {
                    **r.drop(["years_402"]).to_dict(),
                    "positive_fyears": ";".join(map(str, good)),
                    "aaer_years": ";".join(map(str, ay)),
                }
            )
            print(f"KEEP {r['edgar_name']:<40} 4.02={r['date_402']} AAER={r['aaer_date']} fy={good}")
        else:
            print(
                f"drop {grp.iloc[0]['edgar_name']:<40} (no named year with a usable pre-event 10-K in both documents)"
            )
            rejected.append(
                {
                    "company": grp.iloc[0]["edgar_name"],
                    "aaer_date": grp.iloc[0]["aaer_date"],
                    "reason": "no fiscal year named in both the Item 4.02 and the SEC order has a usable pre-event original 10-K",
                }
            )
    pd.DataFrame(rejected).to_csv(config.DATA_CASES / "holdout_rejected.csv", index=False)
    out = pd.DataFrame(picks)
    out.to_csv(config.DATA_CASES / "holdout_selected.csv", index=False)
    print(len(out), "holdout cases selected")


if __name__ == "__main__":
    main()
