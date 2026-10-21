"""Discover holdout-case candidates from the SEC AAER list (mechanical rules; review output by hand).

Writes data/cases/aaer_index.csv (company-respondent AAERs since 2012) and
data/cases/candidates.csv (those that resolve to an EDGAR CIK with an Item 4.02 8-K before the AAER).
Requires SEC_USER_AGENT. Usage: python scripts/discover_cases.py
"""

from __future__ import annotations

import re

import pandas as pd

from redflag import config
from redflag.discovery import (
    company_name,
    item_402_section,
    resolve_cik,
    scrape_aaer,
    years_in_year_sentences,
)
from redflag.edgar import ARCHIVES_URL, EdgarClient

FIRST_AAER_DATE = pd.Timestamp("2012-01-01")
FIRST_402_DATE = pd.Timestamp("2010-06-01")  # XBRL begins for the largest filers around mid-2009
FINANCIAL = range(6000, 6800)


def text_of(client: EdgarClient, cik: int, row: dict) -> str:
    import html

    url = ARCHIVES_URL.format(
        cik=cik, acc_nodash=row["accessionNumber"].replace("-", ""), doc=row["primaryDocument"]
    )
    raw = client.get_text(url, f"docs/{row['accessionNumber']}_{row['primaryDocument']}")
    t = re.sub(r"<(script|style).*?</\1>", " ", raw, flags=re.S | re.I)
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", t)))


def main() -> None:
    client = EdgarClient()
    aaer = scrape_aaer(client)
    aaer["company"] = aaer["respondents"].apply(company_name)
    aaer = aaer[aaer["company"].notna() & (aaer["aaer_date"] >= FIRST_AAER_DATE)].reset_index(drop=True)
    aaer.to_csv(config.DATA_CASES / "aaer_index.csv", index=False)
    print(f"{len(aaer)} company-respondent AAERs since {FIRST_AAER_DATE.date()}")

    rows = []
    for _, a in aaer.iterrows():
        ciks = resolve_cik(client, a["company"])
        for cik, disp in ciks:
            try:
                sub = client.submissions(cik)
            except Exception:
                continue
            sic = int(sub.get("sic") or 0)
            if sic in FINANCIAL or sic == 0:
                continue
            filings = client.all_filings(cik)
            for r in filings:
                if not (r["form"].startswith("8-K") and "4.02" in str(r["items"]).split(",")):
                    continue
                d = pd.Timestamp(r["filingDate"])
                if not (FIRST_402_DATE <= d <= a["aaer_date"]) or r["form"] != "8-K":
                    continue
                try:
                    sec = item_402_section(text_of(client, cik, r))
                except Exception:
                    sec = ""
                rows.append(
                    {
                        "aaer_no": a["aaer_no"],
                        "aaer_date": a["aaer_date"].date(),
                        "aaer_title": a["respondents"],
                        "aaer_url": a["url"],
                        "cik": cik,
                        "edgar_name": disp,
                        "sic": sic,
                        "state": sub.get("stateOfIncorporation"),
                        "n_10k": sum(f["form"] == "10-K" for f in filings),
                        "accn_402": r["accessionNumber"],
                        "date_402": r["filingDate"],
                        "years_hint": ";".join(map(str, years_in_year_sentences(sec))),
                        "snippet": sec[:420],
                    }
                )
    out = pd.DataFrame(rows).drop_duplicates(["aaer_no", "accn_402"])
    out.to_csv(config.DATA_CASES / "candidates.csv", index=False)
    print(f"{out['cik'].nunique()} companies / {len(out)} (AAER, 4.02) pairs")


if __name__ == "__main__":
    main()
