import numpy as np
import pandas as pd
import pytest

from conftest import synthetic_panel
from redflag import scoring
from redflag.validation import (
    case_outcomes,
    cluster_bootstrap,
    confusion_metrics,
    permutation_pvalue,
    ppv_at_prevalence,
    pr_auc,
    roc_auc,
)


def test_confusion_metrics():
    m = confusion_metrics([1, 1, 0, 0, 0], [1, 0, 1, 0, 0])
    assert (m["tp"], m["fp"], m["fn"], m["tn"]) == (1, 1, 1, 2)
    assert m["precision"] == 0.5 and m["recall"] == 0.5 and m["fpr"] == pytest.approx(1 / 3)


def test_ppv_at_prevalence_formula():
    # TPR .5, FPR .1, prevalence 1% -> .005 / (.005 + .099)
    assert ppv_at_prevalence(0.5, 0.1, 0.01) == pytest.approx(0.005 / 0.104)


def test_auc_helpers_handle_single_class():
    assert np.isnan(roc_auc([1, 1], [0.2, 0.3])) and np.isnan(pr_auc([0, 0], [0.2, 0.3]))
    assert roc_auc([0, 1, 0, 1], [0.1, 0.9, 0.2, 0.8]) == 1.0


def test_cluster_bootstrap_resamples_whole_companies_and_keeps_both_classes():
    groups = np.repeat(np.arange(10), 3)
    y = (groups < 4).astype(int)
    seen = []

    def fn(ix):
        seen.append(len(set(y[ix])))
        # every replicate holds an integer number of 3-row company blocks
        assert len(ix) % 3 == 0
        return {"n": float(len(ix))}

    out = cluster_bootstrap(groups, y, fn, n_boot=50, seed=1)
    assert all(v == 2 for v in seen)
    assert out["n"]["estimate"] == 30 and out["n"]["lo"] <= 30 <= out["n"]["hi"]


def test_bootstrap_ci_brackets_estimate_and_is_wide_for_noise():
    rng = np.random.default_rng(3)
    groups = np.repeat(np.arange(20), 3)
    y = (groups < 6).astype(int)
    noise = rng.normal(size=len(y))
    out = cluster_bootstrap(groups, y, lambda ix: {"auc": roc_auc(y[ix], noise[ix])}, n_boot=300)
    est, lo, hi = out["auc"]["estimate"], out["auc"]["lo"], out["auc"]["hi"]
    assert lo <= est <= hi and hi - lo > 0.2


def test_permutation_pvalue_detects_signal_and_not_noise():
    groups = np.repeat(np.arange(20), 2)
    y = (groups < 6).astype(int)
    assert permutation_pvalue(groups, y, y + 0.0, n_perm=300) < 0.01
    noise = np.random.default_rng(0).normal(size=len(y))
    assert permutation_pvalue(groups, y, noise, n_perm=300) > 0.05


def test_loco_score_for_a_company_ignores_its_own_labels():
    panel = synthetic_panel()
    base = scoring.loco_scores(panel, scoring.CORE)
    target = int(panel["cik"].iloc[0])
    flipped = panel.copy()
    flipped.loc[flipped["cik"] == target, "label"] = 1.0 - flipped.loc[flipped["cik"] == target, "label"]
    after = scoring.loco_scores(flipped, scoring.CORE)
    rows = panel["cik"] == target
    np.testing.assert_allclose(base.loc[rows, "score"], after.loc[rows, "score"])
    np.testing.assert_allclose(base.loc[rows, "threshold"], after.loc[rows, "threshold"])


def test_loco_scores_recover_planted_signal():
    panel = synthetic_panel(seed=5, n_case=15, n_ctrl=30)
    sc = scoring.loco_scores(panel, scoring.CORE)
    assert sc["score"].notna().all()
    assert roc_auc(panel["label"].astype(int), sc["score"]) > 0.7


def test_beneish_percentile_threshold_uses_training_controls_only():
    panel = synthetic_panel()
    sc = scoring.beneish_scores(panel, 0.9)
    target = int(panel["cik"].iloc[0])
    others = panel[(panel["cik"] != target) & (panel["label"] == 0)]
    expected = np.quantile(others["mscore"], 0.9)
    assert sc.loc[panel["cik"] == target, "threshold"].iloc[0] == pytest.approx(expected)


def test_case_outcome_lead_time():
    panel = pd.DataFrame(
        {
            "cik": [1, 1, 1],
            "fyear": [2012, 2013, 2014],
            "label": [np.nan, 1.0, 1.0],
            "filed": pd.to_datetime(["2013-03-01", "2014-03-01", "2015-03-01"]),
        }
    )
    scored = pd.DataFrame({"score": [5.0, 1.0, 1.0], "threshold": [0.0, 0.0, 2.0]})
    cases = pd.DataFrame(
        [
            {
                "case_id": "c",
                "cik": 1,
                "company": "C",
                "nonreliance_date": pd.Timestamp("2015-06-01"),
                "cutoff": pd.Timestamp("2015-06-01"),
            }
        ]
    )
    out = case_outcomes(panel, scored, cases).iloc[0]
    # flagged: 2012 (clean year, not counted) and 2013 (misstated); 2014 is below threshold
    assert out["detected"] and out["n_flagged"] == 1
    assert out["first_flag_fyear"] == 2013
    assert out["lead_days"] == (pd.Timestamp("2015-06-01") - pd.Timestamp("2014-03-01")).days
    assert out["lead_years"] == pytest.approx(out["lead_days"] / 365.25)
    assert out["flagged_any_pre_event_10k"]
