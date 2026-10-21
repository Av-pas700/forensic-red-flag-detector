"""Accounting-manipulation screening signals computed from one fiscal year of statements.

Input frames carry current-year columns (``revenue``) and prior-year comparatives
(``revenue_prev``) exactly as produced by :mod:`redflag.statements`.

Signals
-------
* **Beneish (1999) M-score** - eight indices combined with the published coefficients.
* **Accruals quality** - total accruals scaled by average assets (cash-flow approach) and a
  Sloan (1996) style balance-sheet accrual ratio.
* **Cash-flow divergence** - receivables growth minus revenue growth, and the gap between net
  income and operating cash flow.
* **Benford** first-digit MAD / chi-square on the numbers in the filing.

Missing-data policy (documented in docs/methods.md): required inputs missing -> the signal is
NaN; GMI/SGAI/DEPI fall back to the neutral value 1 when only an optional input (COGS, SG&A,
depreciation) is absent, and a missing long-term-debt tag is read as zero. The number of such
substitutions is recorded in ``n_imputed``.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .benford import EXPECTED, MIN_N_RELIABLE, benford_test

#: Beneish (1999) eight-variable model coefficients.
BENEISH_COEF = {
    "const": -4.84,
    "dsri": 0.920,
    "gmi": 0.528,
    "aqi": 0.404,
    "sgi": 0.892,
    "depi": 0.115,
    "sgai": -0.172,
    "tata": 4.679,
    "lvgi": -0.327,
}
#: Commonly used cut-off: M-score above this suggests elevated manipulation risk.
BENEISH_THRESHOLD = -1.78

INDEX_COLS = ["dsri", "gmi", "aqi", "sgi", "depi", "sgai", "lvgi", "tata"]
INDEX_CLIP = (0.0, 10.0)
TATA_CLIP = (-1.0, 1.0)


def _div(a, b) -> pd.Series:
    """Element-wise a / b that returns NaN (never inf) when b is zero or missing."""
    a = pd.Series(a, dtype=float)
    b = pd.Series(b, dtype=float, index=a.index)
    out = a / b.where(b != 0)
    return out.replace([np.inf, -np.inf], np.nan)


def beneish_indices(df: pd.DataFrame) -> pd.DataFrame:
    """Compute the eight Beneish indices (and ``n_imputed``) for each row of ``df``."""
    d = df
    rev, rev0 = d["revenue"], d["revenue_prev"]
    n_imputed = pd.Series(0, index=d.index)

    # DSRI: receivables as a share of sales, year over year
    dsri = _div(_div(d["receivables"], rev), _div(d["receivables_prev"], rev0))
    # Retailers and other cash businesses report no trade receivables: neutral index, flagged.
    dsri_missing = (
        d["receivables"].isna()
        & d["receivables_prev"].isna()
        & d["revenue"].notna()
        & d["revenue_prev"].notna()
    )
    dsri = dsri.mask(dsri_missing, 1.0)
    n_imputed += dsri_missing.astype(int)

    # GMI: prior-year gross margin over current gross margin (>1 = margins deteriorating)
    gm = _div(rev - d["cogs"], rev)
    gm0 = _div(rev0 - d["cogs_prev"], rev0)
    gmi = _div(gm0, gm.where(gm > 0))
    gmi_missing = gmi.isna() & d["revenue"].notna() & d["revenue_prev"].notna()
    gmi = gmi.mask(gmi_missing, 1.0)
    n_imputed += gmi_missing.astype(int)

    # AQI: share of assets that are neither current nor PP&E ("soft" assets)
    aq = 1 - _div(d["current_assets"] + d["ppe"], d["total_assets"])
    aq0 = 1 - _div(d["current_assets_prev"] + d["ppe_prev"], d["total_assets_prev"])
    aqi = _div(aq, aq0)

    sgi = _div(rev, rev0)

    # DEPI: prior depreciation rate over current rate (>1 = slowing depreciation)
    rate = _div(d["dep"], d["dep"] + d["ppe"])
    rate0 = _div(d["dep_prev"], d["dep_prev"] + d["ppe_prev"])
    depi = _div(rate0, rate)
    depi_missing = depi.isna() & d["ppe"].notna() & d["ppe_prev"].notna()
    depi = depi.mask(depi_missing, 1.0)
    n_imputed += depi_missing.astype(int)

    sgai = _div(_div(d["sga"], rev), _div(d["sga_prev"], rev0))
    sgai_missing = sgai.isna() & d["revenue"].notna() & d["revenue_prev"].notna()
    sgai = sgai.mask(sgai_missing, 1.0)
    n_imputed += sgai_missing.astype(int)

    # LVGI: (current liabilities + long-term debt) / total assets, year over year
    ltd = d["lt_debt"].fillna(0.0)
    ltd0 = d["lt_debt_prev"].fillna(0.0)
    n_imputed += (d["lt_debt"].isna() & d["current_liabilities"].notna()).astype(int)
    lev = _div(d["current_liabilities"] + ltd, d["total_assets"])
    lev0 = _div(d["current_liabilities_prev"] + ltd0, d["total_assets_prev"])
    lvgi = _div(lev, lev0)

    # TATA: (income - operating cash flow) / total assets - the cash-flow form of total accruals
    tata = _div(d["net_income"] - d["cfo"], d["total_assets"])

    out = pd.DataFrame(
        {
            "dsri": dsri,
            "gmi": gmi,
            "aqi": aqi,
            "sgi": sgi,
            "depi": depi,
            "sgai": sgai,
            "lvgi": lvgi,
            "tata": tata,
            "n_imputed": n_imputed,
        },
        index=d.index,
    )
    for col in INDEX_COLS[:-1]:
        out[col] = out[col].clip(*INDEX_CLIP)
    out["tata"] = out["tata"].clip(*TATA_CLIP)
    return out


def beneish_mscore(indices: pd.DataFrame) -> pd.Series:
    """M = -4.84 + 0.920 DSRI + 0.528 GMI + 0.404 AQI + 0.892 SGI + 0.115 DEPI
    - 0.172 SGAI + 4.679 TATA - 0.327 LVGI  (NaN if any index is missing)."""
    m = pd.Series(BENEISH_COEF["const"], index=indices.index, dtype=float)
    for col in INDEX_COLS:
        m = m + BENEISH_COEF[col] * indices[col]
    return m


def accrual_signals(df: pd.DataFrame) -> pd.DataFrame:
    """Accruals quality and cash-flow divergence signals."""
    avg_assets = (df["total_assets"] + df["total_assets_prev"]) / 2
    total_accruals = _div(df["net_income"] - df["cfo"], avg_assets)

    # Sloan-style balance-sheet accruals: (dCA - dCash) - (dCL - dDebtCurrent) - Dep
    d_ca = df["current_assets"] - df["current_assets_prev"]
    d_cash = df["cash"] - df["cash_prev"]
    d_cl = df["current_liabilities"] - df["current_liabilities_prev"]
    d_debt = df["debt_current"].fillna(0.0) - df["debt_current_prev"].fillna(0.0)
    sloan = _div((d_ca - d_cash) - (d_cl - d_debt) - df["dep"], avg_assets)

    ar_growth = _div(df["receivables"], df["receivables_prev"]) - 1
    rev_growth = _div(df["revenue"], df["revenue_prev"]) - 1
    out = pd.DataFrame(
        {
            "total_accruals": total_accruals,
            "sloan_accruals": sloan,
            "ar_growth": ar_growth,
            "rev_growth": rev_growth,
            "ar_rev_gap": ar_growth - rev_growth,
            "ni_cfo_gap_rev": _div(df["net_income"] - df["cfo"], df["revenue"]),
        },
        index=df.index,
    )
    # Fixed (not data-driven) bounds so that a handful of near-zero denominators cannot dominate.
    for col in ("total_accruals", "sloan_accruals"):
        out[col] = out[col].clip(-1.0, 1.0)
    for col in ("ar_growth", "rev_growth", "ar_rev_gap", "ni_cfo_gap_rev"):
        out[col] = out[col].clip(-2.0, 2.0)
    return out


def benford_signals(df: pd.DataFrame) -> pd.DataFrame:
    """Benford statistics from the stored first-digit counts ``bd1..bd9``."""
    cols = [f"bd{i}" for i in range(1, 10)]
    rows = []
    for counts in df[cols].to_numpy():
        r = benford_test(counts)
        rows.append(
            {
                "benford_n": r.n,
                "benford_chi2": r.chi2,
                "benford_p": r.p_value,
                "benford_mad": r.mad,
                "benford_reliable": r.n >= MIN_N_RELIABLE,
            }
        )
    return pd.DataFrame(rows, index=df.index)


def compute_features(df: pd.DataFrame) -> pd.DataFrame:
    """All signals appended to the statements frame."""
    idx = beneish_indices(df)
    out = pd.concat([df, idx], axis=1)
    out["mscore"] = beneish_mscore(idx)
    out = pd.concat([out, accrual_signals(df)], axis=1)
    if all(f"bd{i}" in df for i in range(1, 10)):
        out = pd.concat([out, benford_signals(df)], axis=1)
    out["beneish_flag"] = (out["mscore"] > BENEISH_THRESHOLD).where(out["mscore"].notna())
    return out


__all__ = [
    "BENEISH_COEF",
    "BENEISH_THRESHOLD",
    "EXPECTED",
    "INDEX_COLS",
    "accrual_signals",
    "benford_signals",
    "beneish_indices",
    "beneish_mscore",
    "compute_features",
]
