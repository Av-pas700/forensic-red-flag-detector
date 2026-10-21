"""Composite red-flag score: a deliberately small, interpretable logistic regression.

Design choices (all fixed *before* looking at results and never tuned on test folds):

* Feature sets are pre-specified: ``CORE`` (six Beneish/accrual/cash-flow signals) and
  ``EXTENDED`` (adds Benford MAD and the earnings-minus-cash-flow gap).
* ``class_weight="balanced"`` re-weights the rare positive class instead of resampling.
* L2 regularisation strength is fixed at sklearn's default ``C = 1`` - with ~30 positive
  firm-years from ~12 companies there is nothing to tune on without overfitting.
* Features are median-imputed and standardised **inside** each training fold.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from .features import BENEISH_THRESHOLD

CORE = ["dsri", "gmi", "aqi", "sgi", "tata", "ar_rev_gap"]
EXTENDED = CORE + ["benford_mad", "ni_cfo_gap_rev"]
#: Added AFTER seeing that the refitted CORE model under-performed the published M-score, so it is
#: exploratory: the M-score itself (a strong prior from a far larger sample) plus three signals the
#: M-score does not contain. Reported alongside, never used to choose between models.
ANCHORED = ["mscore", "ar_rev_gap", "sloan_accruals", "ni_cfo_gap_rev"]
LR_C = 1.0
FLAG_QUANTILE = 0.90  # flag if above the 90th percentile of *training-fold control* scores


def make_model(c: float = LR_C) -> Pipeline:
    return Pipeline(
        [
            ("impute", SimpleImputer(strategy="median", keep_empty_features=True)),
            ("scale", StandardScaler()),
            ("lr", LogisticRegression(C=c, class_weight="balanced", max_iter=2000)),
        ]
    )


def decision_scores(model: Pipeline, x: pd.DataFrame) -> np.ndarray:
    """Log-odds (monotone in probability); easier to threshold and average than probabilities."""
    return model.decision_function(x)


def loco_scores(
    panel: pd.DataFrame, features: list[str], c: float = LR_C, quantile: float = FLAG_QUANTILE
) -> pd.DataFrame:
    """Leave-one-company-out scores for every scorable row.

    For each company the model is fitted on the labelled rows of *all other companies* and used to
    score every row of the held-out company. The flag threshold is the ``quantile`` of the
    training-fold control scores - derived without touching the held-out company.
    """
    out = pd.DataFrame(index=panel.index, columns=["score", "threshold"], dtype=float)
    labelled = panel["label"].notna()
    for cik, rows in panel.groupby("cik"):
        train = panel[labelled & (panel["cik"] != cik)]
        if train["label"].nunique() < 2:
            continue
        model = make_model(c).fit(train[features], train["label"].astype(int))
        train_scores = decision_scores(model, train[features])
        thr = float(np.quantile(train_scores[train["label"].to_numpy() == 0], quantile))
        out.loc[rows.index, "score"] = decision_scores(model, rows[features])
        out.loc[rows.index, "threshold"] = thr
    return out


def beneish_scores(panel: pd.DataFrame, quantile: float | None = None) -> pd.DataFrame:
    """Baseline: the published M-score. ``quantile=None`` uses the fixed -1.78 cut-off; otherwise the
    cut-off is the training-fold control quantile (leave-one-company-out), for a like-for-like test."""
    out = pd.DataFrame({"score": panel["mscore"], "threshold": BENEISH_THRESHOLD}, index=panel.index)
    if quantile is None:
        return out
    labelled = panel["label"].notna() & panel["mscore"].notna()
    for cik, rows in panel.groupby("cik"):
        train = panel[labelled & (panel["cik"] != cik)]
        ctrl = train.loc[train["label"] == 0, "mscore"]
        out.loc[rows.index, "threshold"] = float(np.quantile(ctrl, quantile))
    return out


def fit_full(panel: pd.DataFrame, features: list[str], c: float = LR_C) -> pd.DataFrame:
    """Fit on all labelled rows and return standardised coefficients (descriptive only)."""
    lab = panel[panel["label"].notna()]
    model = make_model(c).fit(lab[features], lab["label"].astype(int))
    coef = model.named_steps["lr"].coef_[0]
    return pd.DataFrame({"feature": features, "std_coefficient": coef}).sort_values(
        "std_coefficient", ascending=False
    )
