"""Frozen-rule evaluation on the holdout cohort (see docs/preregistration.md).

The development cases (picked from memory, inspected while modelling) fit the composite once; the
holdout cases (picked mechanically from SEC's AAER list) only *score* with those frozen rules.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import scoring
from .features import BENEISH_THRESHOLD
from .validation import (
    case_outcomes,
    cluster_bootstrap,
    confusion_metrics,
    permutation_pvalue,
    pr_auc,
    roc_auc,
)


def frozen_scores(panel: pd.DataFrame, dev_ids: list[str], features: list[str] = scoring.CORE) -> dict:
    """Score every row with models fitted on development-cohort labelled rows only."""
    dev = panel[panel["case_id"].isin(dev_ids) & panel["label"].notna()]
    model = scoring.make_model().fit(dev[features], dev["label"].astype(int))
    dev_scores = scoring.decision_scores(model, dev[features])
    thr = float(np.quantile(dev_scores[dev["label"].to_numpy() == 0], scoring.FLAG_QUANTILE))
    core = pd.DataFrame(
        {"score": scoring.decision_scores(model, panel[features]), "threshold": thr}, index=panel.index
    )
    beneish = pd.DataFrame({"score": panel["mscore"], "threshold": BENEISH_THRESHOLD}, index=panel.index)
    return {"core": core, "beneish_fixed": beneish}


def evaluate_holdout(panel: pd.DataFrame, cases: pd.DataFrame, n_boot: int = 2000) -> dict:
    dev_ids = cases.loc[cases["cohort"] == "development", "case_id"].tolist()
    hold_cases = cases[cases["cohort"] == "holdout"]
    hold_ids = hold_cases["case_id"].tolist()
    scored = frozen_scores(panel, dev_ids)

    hold = panel[panel["case_id"].isin(hold_ids) & panel["label"].notna()]
    y = hold["label"].to_numpy().astype(int)
    groups = hold["cik"].to_numpy()
    sc = {k: scored[k].loc[hold.index, "score"].to_numpy() for k in scored}
    fl = {
        k: (scored[k].loc[hold.index, "score"] > scored[k].loc[hold.index, "threshold"]).to_numpy()
        for k in scored
    }

    def fn(ix):
        out = {}
        for k in sc:
            out[f"{k}.roc_auc"] = roc_auc(y[ix], sc[k][ix])
            out[f"{k}.pr_auc"] = pr_auc(y[ix], sc[k][ix])
            cm = confusion_metrics(y[ix], fl[k][ix])
            out[f"{k}.precision"], out[f"{k}.recall"], out[f"{k}.fpr"] = (
                cm["precision"],
                cm["recall"],
                cm["fpr"],
            )
        out["diff_auc.core_minus_beneish"] = out["core.roc_auc"] - out["beneish_fixed.roc_auc"]
        return out

    metrics = cluster_bootstrap(groups, y, fn, n_boot=n_boot, seed=11)
    perm = {k: permutation_pvalue(groups, y, sc[k], seed=13) for k in sc}

    lead = {}
    outcomes = {}
    for k in scored:
        oc = case_outcomes(panel, scored[k], hold_cases)
        outcomes[k] = oc
        det = oc[oc["detected"]]
        lead[k] = {
            "n_cases": int(len(oc)),
            "n_detected": int(oc["detected"].sum()),
            "median_lead_years": float(det["lead_years"].median()) if len(det) else None,
            "max_lead_years": float(det["lead_years"].max()) if len(det) else None,
        }
    return {
        "results": {
            "n_cases": int(len(hold_cases)),
            "n_controls": int(
                panel.loc[panel["case_id"].isin(hold_ids) & (panel["role"] == "control"), "cik"].nunique()
            ),
            "n_positive_rows": int((y == 1).sum()),
            "n_negative_rows": int((y == 0).sum()),
            "positive_share": float((y == 1).mean()),
            "frozen_threshold_core": float(scored["core"]["threshold"].iloc[0]),
            "metrics": metrics,
            "permutation_p": perm,
            "lead": lead,
        },
        "outcomes": outcomes,
        "scored": scored,
        "index": hold.index,
    }
