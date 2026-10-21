"""Case-set loading and *verification against EDGAR*.

``data/cases/cases.csv`` is hand-curated from primary sources. :func:`verify_cases` re-checks the
machine-checkable parts against EDGAR on every build: that the cited accession exists, is an 8-K
carrying Item 4.02, and was filed on the stated date. It also looks up any bankruptcy (Item 1.03)
8-K, so "collapse" status comes from a filing rather than from memory.
"""

from __future__ import annotations

import pandas as pd

from . import config
from .edgar import ARCHIVES_URL, EdgarClient

CASES_CSV = config.DATA_CASES / "cases.csv"


def load_cases(path=CASES_CSV) -> pd.DataFrame:
    df = pd.read_csv(path, dtype={"first_signal_accn": str, "first_signal_date": str})
    df["nonreliance_date"] = pd.to_datetime(df["nonreliance_date"])
    df["first_signal_date"] = pd.to_datetime(df["first_signal_date"])
    df["enforcement_date"] = pd.to_datetime(df["enforcement_date"])
    df["positive_fyears"] = (
        df["positive_fyears"].astype(str).str.split(";").apply(lambda xs: [int(x) for x in xs])
    )
    #: Look-ahead cut-off: only filings strictly before the earliest verified public signal.
    df["cutoff"] = df[["nonreliance_date", "first_signal_date"]].min(axis=1)
    return df


def _doc_url(row: dict, cik: int) -> str:
    return ARCHIVES_URL.format(
        cik=cik, acc_nodash=row["accessionNumber"].replace("-", ""), doc=row["primaryDocument"]
    )


def verify_cases(client: EdgarClient, cases: pd.DataFrame) -> pd.DataFrame:
    """Return ``cases`` with verified URLs and bankruptcy dates; raise if a citation is wrong."""
    out = cases.copy()
    nr_urls, fs_urls, bk_dates, bk_urls = [], [], [], []
    for _, c in cases.iterrows():
        cik = int(c["cik"])
        by_acc = {r["accessionNumber"]: r for r in client.all_filings(cik)}
        nr = by_acc.get(c["nonreliance_accn"])
        if nr is None:
            raise ValueError(f"{c['case_id']}: accession {c['nonreliance_accn']} not found on EDGAR")
        items = str(nr["items"]).split(",")
        if "4.02" not in items or pd.Timestamp(nr["filingDate"]) != c["nonreliance_date"]:
            raise ValueError(
                f"{c['case_id']}: {c['nonreliance_accn']} is not a 4.02 filed on "
                f"{c['nonreliance_date'].date()} (EDGAR says {nr['filingDate']} {items})"
            )
        nr_urls.append(_doc_url(nr, cik))
        if isinstance(c["first_signal_accn"], str) and c["first_signal_accn"]:
            fs = by_acc.get(c["first_signal_accn"])
            if fs is None or pd.Timestamp(fs["filingDate"]) != c["first_signal_date"]:
                raise ValueError(f"{c['case_id']}: first-signal filing does not match EDGAR")
            fs_urls.append(_doc_url(fs, cik))
        else:
            fs_urls.append("")
        bk = [
            r
            for r in by_acc.values()
            if r["form"].startswith("8-K")
            and "1.03" in str(r["items"]).split(",")
            and pd.Timestamp(r["filingDate"]) > c["nonreliance_date"]
        ]
        if bk:
            first = min(bk, key=lambda r: r["filingDate"])
            bk_dates.append(pd.Timestamp(first["filingDate"]))
            bk_urls.append(_doc_url(first, cik))
        else:
            bk_dates.append(pd.NaT)
            bk_urls.append("")
    out["nonreliance_url"] = nr_urls
    out["first_signal_url"] = fs_urls
    out["bankruptcy_date"] = bk_dates
    out["bankruptcy_url"] = bk_urls
    return out
