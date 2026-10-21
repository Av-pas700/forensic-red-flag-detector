"""Panel construction, look-ahead guard, metrics and cluster-bootstrap confidence intervals."""

from __future__ import annotations

from collections.abc import Callable

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, roc_auc_score

from .features import compute_features

MAX_IMPUTED = 2


def build_panel(fin: pd.DataFrame, companies: pd.DataFrame, cases: pd.DataFrame) -> pd.DataFrame:
    """Feature panel with labels.

    Look-ahead guard: for a case company only 10-Ks **filed strictly before** its cut-off (the earlier
    of the Item 4.02 date and the first verified public signal) survive. Labels:

    * case row, fiscal year named in the non-reliance period -> 1
    * control row, fiscal year equal to a misstated year of its matched case -> 0
    * everything else -> NaN (scored for display but never used to fit or evaluate)
    """
    fin = fin.copy()
    for col in ("fye", "filed", "fye_prev"):
        fin[col] = pd.to_datetime(fin[col])
    panel = compute_features(fin).merge(companies[["cik", "name", "role", "case_id", "sic"]], on="cik")
    cases = cases.set_index("case_id")

    cutoff = panel["case_id"].map(cases["cutoff"])
    is_case = panel["role"] == "case"
    panel = panel[~(is_case & (panel["filed"] >= cutoff.where(is_case)))].copy()

    positives = panel["case_id"].map(cases["positive_fyears"])
    panel["in_window"] = [
        fy in (yrs if isinstance(yrs, list) else [])
        for fy, yrs in zip(panel["fyear"], positives, strict=True)
    ]
    panel["label"] = np.where(panel["in_window"], np.where(panel["role"] == "case", 1.0, 0.0), np.nan)
    panel = panel[panel["mscore"].notna() & (panel["n_imputed"] <= MAX_IMPUTED)]
    return panel.reset_index(drop=True)


def assert_no_lookahead(panel: pd.DataFrame, cases: pd.DataFrame) -> None:
    """Raise if any case-company row was filed on/after its cut-off date."""
    cut = cases.set_index("cik")["cutoff"]
    for cik, rows in panel[panel["role"] == "case"].groupby("cik"):
        late = rows[rows["filed"] >= cut[cik]]
        if len(late):
            raise AssertionError(f"look-ahead leak for CIK {cik}: {late['filed'].tolist()}")


# ----------------------------------------------------------------------------- metrics
def roc_auc(y, s) -> float:
    return float(roc_auc_score(y, s)) if len(set(y)) == 2 else np.nan


def pr_auc(y, s) -> float:
    """Average precision (area under the precision-recall step curve)."""
    return float(average_precision_score(y, s)) if len(set(y)) == 2 else np.nan


def ppv_at_prevalence(tpr: float, fpr: float, prevalence: float) -> float:
    """Precision implied by a given TPR/FPR if only ``prevalence`` of firms are manipulators."""
    denom = tpr * prevalence + fpr * (1 - prevalence)
    return float(tpr * prevalence / denom) if denom > 0 else np.nan


def confusion_metrics(y, flag) -> dict[str, float]:
    y = np.asarray(y).astype(bool)
    flag = np.asarray(flag).astype(bool)
    tp, fp = int((flag & y).sum()), int((flag & ~y).sum())
    fn, tn = int((~flag & y).sum()), int((~flag & ~y).sum())
    return {
        "precision": tp / (tp + fp) if tp + fp else np.nan,
        "recall": tp / (tp + fn) if tp + fn else np.nan,
        "fpr": fp / (fp + tn) if fp + tn else np.nan,
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
    }


def cluster_bootstrap(
    groups: np.ndarray,
    y: np.ndarray,
    fn: Callable[[np.ndarray], dict[str, float]],
    n_boot: int = 2000,
    seed: int = 42,
    alpha: float = 0.05,
) -> dict[str, dict[str, float]]:
    """Percentile CIs from resampling whole companies (rows within a company are correlated).

    Case companies and control companies are resampled separately so every replicate contains both
    classes. ``fn`` receives the integer row positions of a replicate and returns named metrics.
    """
    rng = np.random.default_rng(seed)
    y = np.asarray(y)
    by_group = {g: np.flatnonzero(groups == g) for g in np.unique(groups)}
    case_g = [g for g, ix in by_group.items() if y[ix].max() == 1]
    ctrl_g = [g for g in by_group if g not in set(case_g)]
    point = fn(np.arange(len(y)))
    draws: dict[str, list[float]] = {k: [] for k in point}
    for _ in range(n_boot):
        pick = list(rng.choice(case_g, len(case_g))) + list(rng.choice(ctrl_g, len(ctrl_g)))
        ix = np.concatenate([by_group[g] for g in pick])
        res = fn(ix)
        for k, v in res.items():
            draws[k].append(v)
    out = {}
    for k, est in point.items():
        arr = np.asarray(draws[k], dtype=float)
        arr = arr[np.isfinite(arr)]
        lo, hi = np.quantile(arr, [alpha / 2, 1 - alpha / 2]) if len(arr) else (np.nan, np.nan)
        out[k] = {"estimate": float(est), "lo": float(lo), "hi": float(hi)}
    return out


def permutation_pvalue(
    groups: np.ndarray, y: np.ndarray, s: np.ndarray, n_perm: int = 5000, seed: int = 7
) -> float:
    """P(AUC >= observed) when case/control labels are shuffled across *companies*."""
    rng = np.random.default_rng(seed)
    uniq = np.unique(groups)
    is_case = np.array([y[groups == g].max() == 1 for g in uniq])
    obs = roc_auc(y, s)
    ge = 0
    for _ in range(n_perm):
        perm = rng.permutation(is_case)
        lab = dict(zip(uniq, perm, strict=True))
        y_perm = np.array([int(lab[g]) for g in groups])
        if len(set(y_perm)) < 2:
            continue
        ge += roc_auc(y_perm, s) >= obs
    return float((ge + 1) / (n_perm + 1))


# ----------------------------------------------------------------------------- case-level
def case_outcomes(panel: pd.DataFrame, scored: pd.DataFrame, cases: pd.DataFrame) -> pd.DataFrame:
    """Per-case detection and lead time using out-of-company scores.

    ``lead_*`` is measured from the **filing date of the earliest flagged misstated-year 10-K** to the
    case cut-off (earlier of 4.02 date / first verified signal); ``lead_to_4_02_*`` uses the 4.02 date.
    """
    flag = scored["score"] > scored["threshold"]
    rows = []
    for _, c in cases.iterrows():
        mine = panel[panel["cik"] == int(c["cik"])]
        mis = mine[mine["label"] == 1]
        hit = mis[flag.loc[mis.index]]
        any_flag = mine[flag.loc[mine.index]]
        row = {
            "case_id": c["case_id"],
            "company": c["company"],
            "n_misstated_10k": len(mis),
            "n_flagged": len(hit),
            "detected": bool(len(hit)),
            "first_flag_filed": hit["filed"].min() if len(hit) else pd.NaT,
            "first_flag_fyear": int(hit.loc[hit["filed"].idxmin(), "fyear"]) if len(hit) else None,
            "flagged_any_pre_event_10k": bool(len(any_flag)),
            "n_pre_event_10k": len(mine),
        }
        if len(hit):
            first = hit["filed"].min()
            row["lead_days"] = (c["cutoff"] - first).days
            row["lead_to_4_02_days"] = (c["nonreliance_date"] - first).days
            row["lead_years"] = row["lead_days"] / 365.25
            row["lead_quarters"] = row["lead_days"] / 91.3125
        rows.append(row)
    return pd.DataFrame(rows)
