"""Healthy-peer control selection.

For each case company we pick ``per_case`` controls that are:

* US-located 10-K filers with XBRL data (XBRL ``frames`` API, ``loc`` starts with "US");
* in the same 2-digit SIC industry (fallback: same SIC division, logged in the output);
* not financial companies (SIC 6000-6799);
* of similar size - nearest in log total assets at the case's first misstated fiscal year end,
  within a factor of 4;
* never the subject of an Item 4.02 non-reliance 8-K in their entire EDGAR history;
* with a usable 10-K (valid Beneish inputs) for every fiscal year the matched case is labelled
  positive, so controls and cases are compared in the *same fiscal years*.

Each control is used for one case only. Selection is deterministic: candidates are tried in order
of closeness in size.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .edgar import EdgarClient
from .features import beneish_indices
from .statements import extract_annual_statements

FINANCIAL_SIC = range(6000, 6800)
SIC_DIVISIONS = [
    (100, 999),
    (1000, 1499),
    (1500, 1799),
    (2000, 3999),
    (4000, 4999),
    (5000, 5199),
    (5200, 5999),
    (6000, 6799),
    (7000, 8999),
    (9100, 9999),
]
MAX_CANDIDATES = 500
SIZE_BAND = 4.0


def sic_division(sic: int) -> int:
    for i, (lo, hi) in enumerate(SIC_DIVISIONS):
        if lo <= sic <= hi:
            return i
    return -1


def frame_period(fye: pd.Timestamp) -> str:
    """Nearest calendar quarter-end instant frame, e.g. 2012-01-31 -> CY2011Q4I."""
    best = None
    for year in (fye.year - 1, fye.year):
        for q, (m, d) in enumerate([(3, 31), (6, 30), (9, 30), (12, 31)], start=1):
            gap = abs((pd.Timestamp(year, m, d) - fye).days)
            if best is None or gap < best[0]:
                best = (gap, f"CY{year}Q{q}I")
    return best[1]


def usable_years(stm: pd.DataFrame, fyears: list[int]) -> bool:
    """True if every requested fiscal year has a 10-K with all required Beneish inputs."""
    if stm.empty:
        return False
    idx = beneish_indices(stm)
    ok = idx[["dsri", "aqi", "sgi", "lvgi", "tata"]].notna().all(axis=1) & (idx["n_imputed"] <= 2)
    have = set(stm.loc[ok, "fyear"])
    return all(y in have for y in fyears)


def missing_inputs(stm: pd.DataFrame, fyears: list[int]) -> str:
    """Human-readable list of Beneish indices that cannot be computed for the given years."""
    if stm.empty:
        return "no 10-K rows"
    idx = beneish_indices(stm[stm["fyear"].isin(fyears)])
    bad = [c for c in ("dsri", "aqi", "sgi", "lvgi", "tata") if idx[c].isna().any()]
    if (idx["n_imputed"] > 2).any():
        bad.append("n_imputed>2")
    absent = sorted(set(fyears) - set(stm["fyear"]))
    return ", ".join(bad) + (f"; no 10-K for fyear {absent}" if absent else "") or "unknown"


def select_controls(
    client: EdgarClient, case: pd.Series, case_stm: pd.DataFrame, exclude_ciks: set[int], per_case: int = 3
) -> list[dict]:
    fyears = sorted(case["positive_fyears"])
    ref = case_stm[case_stm["fyear"] == fyears[0]]
    if ref.empty:
        raise ValueError(f"{case['case_id']}: no 10-K for reference year {fyears[0]}")
    ref = ref.iloc[0]
    case_sic = int(client.submissions(int(case["cik"])).get("sic") or 0)
    frame = pd.DataFrame(client.frame("Assets", "USD", frame_period(ref["fye"])))
    frame = frame[frame["loc"].fillna("").str.startswith("US") & (frame["val"] > 0)]
    frame["dist"] = np.abs(np.log(frame["val"] / ref["total_assets"]))
    frame = frame[frame["dist"] <= np.log(SIZE_BAND)].sort_values("dist")
    frame = frame[~frame["cik"].isin(exclude_ciks)].drop_duplicates("cik")

    # Rank candidates by (industry tier, size distance): 3-digit SIC, then 2-digit, then division.
    pool = []
    for _, cand in frame.head(MAX_CANDIDATES).iterrows():
        cik = int(cand["cik"])
        try:
            sic = int(client.submissions(cik).get("sic") or 0)
        except Exception:
            continue
        if sic in FINANCIAL_SIC or sic == 0:
            continue
        if sic // 10 == case_sic // 10:
            tier = 0
        elif sic // 100 == case_sic // 100:
            tier = 1
        elif sic_division(sic) == sic_division(case_sic):
            tier = 2
        else:
            continue
        pool.append((tier, float(cand["dist"]), cik, sic, cand["entityName"]))
    pool.sort()

    chosen: list[dict] = []
    for tier, dist, cik, sic, name in pool:
        if len(chosen) >= per_case:
            break
        filings = client.all_filings(cik)
        if any(r["form"].startswith("8-K") and "4.02" in str(r["items"]).split(",") for r in filings):
            continue
        try:
            stm = extract_annual_statements(client.company_facts(cik), cik)
        except Exception:
            continue
        if not usable_years(stm, fyears):
            continue
        chosen.append(
            {
                "cik": cik,
                "name": name,
                "sic": sic,
                "case_id": case["case_id"],
                "match_level": ("3-digit SIC", "2-digit SIC", "SIC division")[tier],
                "log_size_gap": dist,
            }
        )
    return chosen
