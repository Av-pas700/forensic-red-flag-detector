"""Point-in-time extraction of annual statement items from XBRL ``companyfacts``.

The companyfacts API serves, for every period, every value ever reported - including
numbers later *restated* in subsequent filings. Using those would leak the future into a
"before the restatement" test. To avoid that, each fiscal year is built **only from facts
tagged with the accession number of that year's original 10-K**: the current-year column and
the prior-year comparative column as the company itself presented them on the filing date.
Amended filings (10-K/A) are ignored because they are published after the fact.
"""

from __future__ import annotations

from datetime import date, datetime

import numpy as np
import pandas as pd

# Ordered fallbacks: the first tag that has data in the filing wins.
FLOW_TAGS: dict[str, list[str]] = {
    "revenue": [
        "Revenues",
        "SalesRevenueNet",
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "RevenueFromContractWithCustomerIncludingAssessedTax",
        "SalesRevenueGoodsNet",
        "SalesRevenueServicesNet",
    ],
    "cogs": ["CostOfRevenue", "CostOfGoodsAndServicesSold", "CostOfGoodsSold", "CostOfServices"],
    "sga": ["SellingGeneralAndAdministrativeExpense"],
    "dep": [
        "DepreciationDepletionAndAmortization",
        "DepreciationAndAmortization",
        "DepreciationAmortizationAndAccretionNet",
        "Depreciation",
    ],
    # Consolidated income first: it is the like-for-like partner of consolidated operating cash flow.
    "net_income": ["ProfitLoss", "NetIncomeLoss", "NetIncomeLossAvailableToCommonStockholdersBasic"],
    "income_cont": [
        "IncomeLossFromContinuingOperations",
        "IncomeLossFromContinuingOperationsIncludingPortionAttributableToNoncontrollingInterest",
        "IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest",
    ],
    "cfo": [
        "NetCashProvidedByUsedInOperatingActivities",
        "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations",
    ],
}
STOCK_TAGS: dict[str, list[str]] = {
    "receivables": [
        "AccountsReceivableNetCurrent",
        "ReceivablesNetCurrent",
        "AccountsNotesAndLoansReceivableNetCurrent",
        "AccountsAndOtherReceivablesNetCurrent",
        "AccountsReceivableNet",
    ],
    "current_assets": ["AssetsCurrent"],
    "ppe": [
        "PropertyPlantAndEquipmentNet",
        "PropertyPlantAndEquipmentAndFinanceLeaseRightOfUseAssetAfterAccumulatedDepreciationAndAmortization",  # noqa: E501
    ],
    "total_assets": ["Assets"],
    "current_liabilities": ["LiabilitiesCurrent"],
    "lt_debt": ["LongTermDebtNoncurrent", "LongTermDebt", "LongTermNotesPayable", "ConvertibleNotesPayable"],
    "cash": [
        "CashAndCashEquivalentsAtCarryingValue",
        "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents",
    ],
    "debt_current": ["DebtCurrent", "LongTermDebtCurrent", "ShortTermBorrowings"],
}
METRICS = list(FLOW_TAGS) + list(STOCK_TAGS)

ANNUAL_MIN_DAYS, ANNUAL_MAX_DAYS = 350, 380


def _parse(d: str) -> date:
    return datetime.strptime(d, "%Y-%m-%d").date()


def _annual_filings(us_gaap: dict) -> dict[str, dict]:
    """Map accession -> {filed, fye} for original 10-K filings (not amendments)."""
    candidates: dict[str, dict] = {}
    for tag in (
        "NetIncomeLoss",
        "ProfitLoss",
        "Revenues",
        "SalesRevenueNet",
        "Assets",
        "RevenueFromContractWithCustomerExcludingAssessedTax",
    ):
        for unit_rows in us_gaap.get(tag, {}).get("units", {}).values():
            for r in unit_rows:
                if r.get("form") != "10-K" or "end" not in r:
                    continue
                if "start" in r:
                    days = (_parse(r["end"]) - _parse(r["start"])).days
                    if not ANNUAL_MIN_DAYS <= days <= ANNUAL_MAX_DAYS:
                        continue
                acc = r["accn"]
                info = candidates.setdefault(acc, {"filed": r["filed"], "ends": []})
                info["ends"].append(r["end"])
    out = {}
    for acc, info in candidates.items():
        fye = max(info["ends"])
        # A 10-K cannot describe a period ending after it was filed; guards odd forward-dated facts.
        if fye <= info["filed"]:
            out[acc] = {"filed": info["filed"], "fye": fye}
    return out


def _pick(
    us_gaap: dict, tags: list[str], acc: str, end: str, *, flow: bool, unit: str = "USD"
) -> tuple[float, str] | None:
    """Value of the first tag that reports ``end`` in filing ``acc`` (annual duration if flow)."""
    for tag in tags:
        for r in us_gaap.get(tag, {}).get("units", {}).get(unit, []):
            if r.get("accn") != acc or r.get("end") != end:
                continue
            if flow:
                if "start" not in r:
                    continue
                days = (_parse(r["end"]) - _parse(r["start"])).days
                if not ANNUAL_MIN_DAYS <= days <= ANNUAL_MAX_DAYS:
                    continue
            elif "start" in r:
                continue
            return float(r["val"]), tag
    return None


def _prior_end(us_gaap: dict, acc: str, fye: str) -> str | None:
    """Prior-year period end as presented in the same filing (closest to one year earlier)."""
    target = _parse(fye)
    best, best_gap = None, 99
    for tag in ("Assets", "NetIncomeLoss", "ProfitLoss", "Revenues", "SalesRevenueNet"):
        for r in us_gaap.get(tag, {}).get("units", {}).get("USD", []):
            if r.get("accn") != acc or "end" not in r:
                continue
            gap = abs((target - _parse(r["end"])).days - 365)
            if gap < best_gap and (target - _parse(r["end"])).days > 300:
                best, best_gap = r["end"], gap
    return best if best_gap <= 20 else None


def benford_counts(us_gaap: dict, acc: str, ends: tuple[str, str | None]) -> list[int]:
    """First-digit counts of distinct |USD| values reported in filing ``acc`` for its two periods."""
    seen: set[tuple[str, str]] = set()
    counts = [0] * 9
    for tag, body in us_gaap.items():
        for r in body.get("units", {}).get("USD", []):
            if r.get("accn") != acc or r.get("end") not in ends:
                continue
            key = (tag, r["end"] + r.get("start", ""))
            if key in seen:
                continue
            seen.add(key)
            v = abs(float(r["val"]))
            if v >= 10:  # sub-$10 amounts are rounding residue, not reported magnitudes
                counts[int(str(int(v))[0]) - 1] += 1
    return counts


def extract_annual_statements(facts: dict, cik: int | None = None) -> pd.DataFrame:
    """One row per original 10-K: current (``x``) and prior-year (``x_prev``) statement items.

    Only data published in that filing is used (see module docstring). ``tag_<metric>`` records
    which XBRL tag supplied the current-year value, for auditability.
    """
    us_gaap = facts.get("facts", {}).get("us-gaap", {})
    rows = []
    for acc, info in _annual_filings(us_gaap).items():
        fye = info["fye"]
        prev = _prior_end(us_gaap, acc, fye)
        row: dict = {
            "cik": cik if cik is not None else facts.get("cik"),
            "accn": acc,
            "filed": info["filed"],
            "fye": fye,
            "fye_prev": prev,
        }
        for metrics, flow in ((FLOW_TAGS, True), (STOCK_TAGS, False)):
            for name, tags in metrics.items():
                cur = _pick(us_gaap, tags, acc, fye, flow=flow)
                row[name] = cur[0] if cur else np.nan
                row[f"tag_{name}"] = cur[1] if cur else None
                pri = None
                if prev:
                    # Prefer the tag used for the current year so both columns are like-for-like.
                    ordered = ([cur[1]] if cur else []) + [t for t in tags if not cur or t != cur[1]]
                    pri = _pick(us_gaap, ordered, acc, prev, flow=flow)
                row[f"{name}_prev"] = pri[0] if pri else np.nan
        counts = benford_counts(us_gaap, acc, (fye, prev))
        for d, c in enumerate(counts, start=1):
            row[f"bd{d}"] = c
        rows.append(row)
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df["fye"] = pd.to_datetime(df["fye"])
    df["filed"] = pd.to_datetime(df["filed"])
    df["fye_prev"] = pd.to_datetime(df["fye_prev"])
    # Fiscal-year label: retailers with a January year-end belong to the prior calendar year.
    df["fyear"] = np.where(df["fye"].dt.month >= 3, df["fye"].dt.year, df["fye"].dt.year - 1)
    df = df.sort_values("fye").drop_duplicates("fye", keep="first").reset_index(drop=True)
    return df
