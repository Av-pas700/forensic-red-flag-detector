"""Universe base-rate check: what share of *all* US filers does the M-score flag?

Uses the XBRL ``frames`` API (one value per company per calendar period) so no per-company download
is needed. Only calendar-year filers are captured (frames align to calendar periods). A company is
scored only if every required Beneish input exists with one consistent XBRL tag in both years, which
also drops banks and insurers (no classified balance sheet). Values are as currently reported, so
this is a base-rate check, not a point-in-time backtest.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .edgar import EdgarClient
from .features import BENEISH_THRESHOLD, beneish_indices, beneish_mscore
from .statements import FLOW_TAGS, STOCK_TAGS


def _frame(client: EdgarClient, tag: str, period: str) -> pd.DataFrame:
    try:
        data = client.frame(tag, "USD", period)
    except Exception:
        return pd.DataFrame(columns=["cik", "val"])
    df = pd.DataFrame(data)
    if df.empty:
        return pd.DataFrame(columns=["cik", "val"])
    df = df[df["loc"].fillna("").str.startswith("US")]
    return df.drop_duplicates("cik").set_index("cik")[["val"]]


def build_universe(client: EdgarClient, year: int) -> pd.DataFrame:
    cur_flow, prev_flow = f"CY{year}", f"CY{year - 1}"
    cur_stock, prev_stock = f"CY{year}Q4I", f"CY{year - 1}Q4I"
    cols = {}
    for tags, (pc, pp) in ((FLOW_TAGS, (cur_flow, prev_flow)), (STOCK_TAGS, (cur_stock, prev_stock))):
        for metric, tag_list in tags.items():
            if metric == "income_cont":
                continue
            chosen = None
            for tag in tag_list:
                a, b = _frame(client, tag, pc), _frame(client, tag, pp)
                both = a.join(b, how="inner", lsuffix="", rsuffix="_prev")
                if chosen is None:
                    chosen = both.rename(columns={"val": metric, "val_prev": f"{metric}_prev"})
                else:  # fill companies still missing with the next tag, same tag in both years
                    extra = both.rename(columns={"val": metric, "val_prev": f"{metric}_prev"})
                    chosen = pd.concat([chosen, extra[~extra.index.isin(chosen.index)]])
            cols[metric] = chosen if chosen is not None else pd.DataFrame(columns=[metric, f"{metric}_prev"])
    df = pd.concat(cols.values(), axis=1)
    df["income_cont"] = np.nan
    df["income_cont_prev"] = np.nan
    return df


def flag_rate(df: pd.DataFrame, threshold: float = BENEISH_THRESHOLD, max_imputed: int = 2) -> dict:
    required = [
        "revenue",
        "revenue_prev",
        "receivables",
        "receivables_prev",
        "current_assets",
        "current_assets_prev",
        "ppe",
        "ppe_prev",
        "total_assets",
        "total_assets_prev",
        "current_liabilities",
        "current_liabilities_prev",
        "net_income",
        "cfo",
    ]
    ok = df.dropna(subset=required)
    ok = ok[(ok["revenue"] > 0) & (ok["revenue_prev"] > 0) & (ok["total_assets"] > 0)]
    idx = beneish_indices(ok)
    m = beneish_mscore(idx)
    scorable = m.notna() & (idx["n_imputed"] <= max_imputed)
    m = m[scorable]
    return {
        "n_universe_with_assets": int(df["total_assets"].notna().sum()),
        "n_scored": int(len(m)),
        "flag_share": float((m > threshold).mean()),
        "p50": float(m.median()),
        "p90": float(m.quantile(0.90)),
    }
