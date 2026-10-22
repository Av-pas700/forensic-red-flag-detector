"""End-to-end analysis: scoring variants, validation metrics, case-level lead times."""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import scoring
from .benford import MIN_N_RELIABLE
from .features import BENEISH_THRESHOLD
from .validation import (
    case_outcomes,
    cluster_bootstrap,
    confusion_metrics,
    permutation_pvalue,
    ppv_at_prevalence,
    pr_auc,
    roc_auc,
)

VARIANTS = {
    "beneish_fixed": "Beneish M-score, fixed -1.78 cut-off (baseline)",
    "beneish_p90": "Beneish M-score, cut-off = 90th pct of training controls",
    "core": "Composite (6 signals), logistic regression",
    "extended": "Composite + Benford MAD + NI-CFO gap",
    "anchored": "Exploratory (post hoc): M-score + AR/revenue gap + Sloan accruals + NI-CFO gap",
}
LR_VARIANTS = ("core", "extended", "anchored")
SINGLE_SIGNALS = [
    "mscore_ops",
    "tata_ops",
    "mscore",
    "dsri",
    "gmi",
    "aqi",
    "sgi",
    "depi",
    "sgai",
    "lvgi",
    "tata",
    "total_accruals",
    "sloan_accruals",
    "ar_rev_gap",
    "ni_cfo_gap_rev",
    "benford_mad",
]
PREVALENCES = (0.01, 0.05)
N_BOOT = 2000


def score_variants(panel: pd.DataFrame) -> dict[str, pd.DataFrame]:
    return {
        "beneish_fixed": scoring.beneish_scores(panel, None),
        "beneish_p90": scoring.beneish_scores(panel, scoring.FLAG_QUANTILE),
        "core": scoring.loco_scores(panel, scoring.CORE),
        "extended": scoring.loco_scores(panel, scoring.EXTENDED),
        "anchored": scoring.loco_scores(panel, scoring.ANCHORED),
    }


def _metrics_fn(y, scores, flags):
    """Closure returning named metrics for a bootstrap replicate (row positions ``ix``)."""

    def fn(ix):
        out = {}
        for name in scores:
            s, f, yy = scores[name][ix], flags[name][ix], y[ix]
            out[f"{name}.roc_auc"] = roc_auc(yy, s)
            out[f"{name}.pr_auc"] = pr_auc(yy, s)
            cm = confusion_metrics(yy, f)
            out[f"{name}.precision"], out[f"{name}.recall"], out[f"{name}.fpr"] = (
                cm["precision"],
                cm["recall"],
                cm["fpr"],
            )
        for name in LR_VARIANTS:
            out[f"diff_auc.{name}_minus_beneish"] = out[f"{name}.roc_auc"] - out["beneish_fixed.roc_auc"]
        return out

    return fn


def _single_auc(values, y):
    def fn(ix):
        return {"roc_auc": roc_auc(y[ix], values[ix])}

    return fn


def run_analysis(panel: pd.DataFrame, cases: pd.DataFrame, n_boot: int = N_BOOT) -> dict:
    scored = score_variants(panel)
    lab = panel["label"].notna()
    for sc in scored.values():
        lab &= sc["score"].notna()
    ev = panel[lab]
    y = ev["label"].to_numpy().astype(int)
    groups = ev["cik"].to_numpy()

    scores = {k: scored[k].loc[ev.index, "score"].to_numpy() for k in scored}
    flags = {
        k: (scored[k].loc[ev.index, "score"] > scored[k].loc[ev.index, "threshold"]).to_numpy()
        for k in scored
    }

    boot = cluster_bootstrap(groups, y, _metrics_fn(y, scores, flags), n_boot=n_boot)
    perm = {k: permutation_pvalue(groups, y, scores[k]) for k in ("beneish_fixed", *LR_VARIANTS)}

    # -- single-signal discrimination (raw AUC, higher signal = riskier; <0.5 means reverse direction)
    singles = {}
    for sig in SINGLE_SIGNALS:
        ok = ev[sig].notna().to_numpy()
        if ok.sum() < 10 or len(set(y[ok])) < 2:
            continue
        sig_vals, y_ok = ev[sig].to_numpy()[ok], y[ok]
        b = cluster_bootstrap(groups[ok], y_ok, _single_auc(sig_vals, y_ok), n_boot=500)
        singles[sig] = {"n": int(ok.sum()), **b["roc_auc"]}

    # -- sensitivity: TATA from income from continuing operations instead of net income
    ops = ev["mscore_ops"].to_numpy()
    base_m = ev["mscore"].to_numpy()

    def _ops_fn(ix):
        return {
            "diff": roc_auc(y[ix], ops[ix]) - roc_auc(y[ix], base_m[ix]),
            "auc_ops": roc_auc(y[ix], ops[ix]),
        }

    sens_ops = cluster_bootstrap(groups, y, _ops_fn, n_boot=n_boot, seed=21)

    case_of = ev["case_id"].to_numpy()
    # -- exploratory (post hoc): does the screen work only for revenue/receivable-type restatements?
    by_type: dict[str, dict] = {}
    if "issue_type" in cases:
        tmap = cases.set_index("case_id")["issue_type"]
        ev_type = ev["case_id"].map(tmap).to_numpy()
        for t in ("revenue", "other"):
            sel = ev_type == t
            if sel.sum() == 0 or len(set(y[sel])) < 2:
                continue

            def _fn(ix, sel=sel):
                yy = y[sel][ix]
                out = {}
                for k in ("beneish_fixed", "core"):
                    out[f"{k}.roc_auc"] = roc_auc(yy, scores[k][sel][ix])
                    cm = confusion_metrics(yy, flags[k][sel][ix])
                    out[f"{k}.recall"], out[f"{k}.fpr"] = cm["recall"], cm["fpr"]
                return out

            b = cluster_bootstrap(groups[sel], y[sel], _fn, n_boot=n_boot, seed=31)
            by_type[t] = {
                "n_cases": int(len(set(case_of[sel & (y == 1)]))),
                "n_positive_rows": int(y[sel].sum()),
                "n_negative_rows": int((1 - y[sel]).sum()),
                **b,
            }

    # -- case-level outcomes and lead times
    outcomes = {k: case_outcomes(panel, scored[k], cases) for k in scored}

    def lead_summary(df):
        det = df[df["detected"]]
        return {
            "n_cases": int(len(df)),
            "n_detected": int(df["detected"].sum()),
            "n_flagged_any_pre_event": int(df["flagged_any_pre_event_10k"].sum()),
            "median_lead_years": float(det["lead_years"].median()) if len(det) else None,
            "min_lead_years": float(det["lead_years"].min()) if len(det) else None,
            "max_lead_years": float(det["lead_years"].max()) if len(det) else None,
            "median_lead_quarters": float(det["lead_quarters"].median()) if len(det) else None,
        }

    lead = {k: lead_summary(v) for k, v in outcomes.items()}

    # -- leave-one-case-out sensitivity of the (out-of-company) AUC
    jack = {}
    for k in ("beneish_fixed", "core", "anchored"):
        vals = []
        for cid in np.unique(case_of):
            keep = case_of != cid
            if len(set(y[keep])) == 2:
                vals.append(roc_auc(y[keep], scores[k][keep]))
        jack[k] = {"min": float(np.min(vals)), "max": float(np.max(vals))}

    # -- prevalence-adjusted precision (an illustrative assumption, not an estimate of real prevalence)
    ppv = {}
    for k in ("beneish_fixed", "core", "anchored"):
        tpr, fpr = boot[f"{k}.recall"]["estimate"], boot[f"{k}.fpr"]["estimate"]
        ppv[k] = {f"{p:.2f}": ppv_at_prevalence(tpr, fpr, p) for p in PREVALENCES}

    # -- Benford
    reliable = ev["benford_n"] >= MIN_N_RELIABLE
    benford = {
        "n_filings_scored": int(panel["benford_n"].notna().sum()),
        "share_reliable_n": float((panel["benford_n"] >= MIN_N_RELIABLE).mean()),
        "median_n_values": float(panel["benford_n"].median()),
        "median_mad_cases": float(ev.loc[(y == 1), "benford_mad"].median()),
        "median_mad_controls": float(ev.loc[(y == 0), "benford_mad"].median()),
        "share_nonconforming_cases": float((ev.loc[(y == 1), "benford_mad"] > 0.015).mean()),
        "share_nonconforming_controls": float((ev.loc[(y == 0), "benford_mad"] > 0.015).mean()),
        "n_reliable_in_eval": int(reliable.sum()),
    }

    coefs = {
        k: scoring.fit_full(panel, f).round(4).to_dict("records")
        for k, f in (("core", scoring.CORE), ("extended", scoring.EXTENDED), ("anchored", scoring.ANCHORED))
    }

    results = {
        "sample": {
            "n_cases": int(cases.shape[0]),
            "n_controls": int(panel.loc[panel["role"] == "control", "cik"].nunique()),
            "n_positive_rows": int((y == 1).sum()),
            "n_negative_rows": int((y == 0).sum()),
            "n_rows_total": int(len(panel)),
            "positive_share": float((y == 1).mean()),
            "fyear_min": int(ev["fyear"].min()),
            "fyear_max": int(ev["fyear"].max()),
        },
        "variants": VARIANTS,
        "metrics": boot,
        "permutation_p": perm,
        "single_signals": singles,
        "lead": lead,
        "jackknife_auc": jack,
        "ppv_at_prevalence": ppv,
        "benford": benford,
        "coefficients": coefs,
        "sensitivity_ops": sens_ops,
        "by_issue_type": by_type,
        "beneish_threshold": BENEISH_THRESHOLD,
        "n_boot": n_boot,
    }
    tables = {
        "case_outcomes_core": outcomes["core"],
        "case_outcomes_anchored": outcomes["anchored"],
        "case_outcomes_beneish": outcomes["beneish_fixed"],
        "case_outcomes_beneish_p90": outcomes["beneish_p90"],
        "case_outcomes_extended": outcomes["extended"],
    }
    return {"results": results, "tables": tables, "scored": scored, "eval_index": ev.index}


def _subset(res: dict) -> dict:
    return {
        "sample": res["sample"],
        "metrics": res["metrics"],
        "lead": res["lead"],
        "permutation_p": res["permutation_p"],
    }


def run_full(panel: pd.DataFrame, cases: pd.DataFrame, n_boot: int = N_BOOT, universe_path=None) -> dict:
    """Pooled leave-one-company-out analysis + development-only replication + frozen holdout test."""
    import json
    from pathlib import Path

    from .holdout import evaluate_holdout

    pooled = run_analysis(panel, cases, n_boot)
    res = pooled["results"]
    tables = dict(pooled["tables"])

    dev_cases = cases[cases["cohort"] == "development"]
    dev = run_analysis(panel[panel["case_id"].isin(dev_cases["case_id"])], dev_cases, n_boot)
    res["development"] = _subset(dev["results"])

    hold = evaluate_holdout(panel, cases, n_boot)
    res["holdout"] = hold["results"]
    for k, df in hold["outcomes"].items():
        tables[f"holdout_outcomes_{k}"] = df

    if universe_path is not None and Path(universe_path).is_file():
        res["universe"] = json.loads(Path(universe_path).read_text())
    return {
        "results": res,
        "tables": tables,
        "scored": pooled["scored"],
        "eval_index": pooled["eval_index"],
        "holdout": hold,
    }
