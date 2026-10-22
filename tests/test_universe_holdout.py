import numpy as np
import pandas as pd

from conftest import synthetic_panel
from redflag.holdout import evaluate_holdout, frozen_scores
from redflag.universe import flag_rate


def _universe(n=200, seed=0):
    rng = np.random.default_rng(seed)
    rev = rng.uniform(100, 1000, n)
    base = {
        "revenue": rev,
        "revenue_prev": rev / 1.1,
        "cogs": rev * 0.6,
        "cogs_prev": rev / 1.1 * 0.6,
        "sga": rev * 0.1,
        "sga_prev": rev / 1.1 * 0.1,
        "dep": rev * 0.03,
        "dep_prev": rev * 0.03,
        "net_income": rev * 0.05,
        "cfo": rev * 0.07,
        "receivables": rev * 0.15,
        "receivables_prev": rev / 1.1 * 0.15,
        "current_assets": rev * 0.5,
        "current_assets_prev": rev * 0.45,
        "ppe": rev * 0.3,
        "ppe_prev": rev * 0.28,
        "total_assets": rev * 1.2,
        "total_assets_prev": rev * 1.1,
        "current_liabilities": rev * 0.3,
        "current_liabilities_prev": rev * 0.28,
        "lt_debt": rev * 0.2,
        "lt_debt_prev": rev * 0.2,
        "income_cont": np.nan,
        "income_cont_prev": np.nan,
    }
    return pd.DataFrame(base, index=pd.RangeIndex(n, name="cik"))


def test_flag_rate_counts_only_scorable_rows_and_is_low_for_healthy_firms():
    df = _universe()
    df.loc[0:9, "total_assets"] = np.nan  # not scorable
    r = flag_rate(df)
    assert r["n_scored"] == 190 and r["n_universe_with_assets"] == 190
    assert r["flag_share"] < 0.05


def test_flag_rate_flags_aggressive_accruals_and_receivables():
    df = _universe()
    df.loc[:49, "receivables"] = df.loc[:49, "receivables"] * 4
    df.loc[:49, "net_income"] = df.loc[:49, "revenue"] * 0.4
    assert flag_rate(df)["flag_share"] >= 0.2


def _cases(panel):
    ids = sorted(panel["case_id"].unique())
    return pd.DataFrame({"case_id": ids, "cohort": ["development"] * 5 + ["holdout"] * (len(ids) - 5)})


def test_frozen_scores_do_not_depend_on_holdout_labels():
    panel = synthetic_panel(seed=3, n_case=10, n_ctrl=20)
    cases = _cases(panel)
    dev_ids = cases.loc[cases["cohort"] == "development", "case_id"].tolist()
    a = frozen_scores(panel, dev_ids)["core"]
    b_panel = panel.copy()
    hold = ~b_panel["case_id"].isin(dev_ids)
    b_panel.loc[hold, "label"] = 1.0 - b_panel.loc[hold, "label"]
    b = frozen_scores(b_panel, dev_ids)["core"]
    pd.testing.assert_frame_equal(a, b)


def test_evaluate_holdout_runs_end_to_end_on_a_synthetic_panel():
    panel = synthetic_panel(seed=4, n_case=12, n_ctrl=24)
    ids = [f"c{i}" for i in range(12)]
    cases = pd.DataFrame(
        {
            "case_id": ids,
            "cik": [1000 + i for i in range(12)],
            "company": ids,
            "cohort": ["development"] * 6 + ["holdout"] * 6,
            "nonreliance_date": pd.Timestamp("2016-01-01"),
            "cutoff": pd.Timestamp("2016-01-01"),
        }
    )
    panel["cohort"] = panel["case_id"].map(cases.set_index("case_id")["cohort"])
    out = evaluate_holdout(panel, cases, n_boot=40)
    r = out["results"]
    assert r["n_cases"] == 6 and r["n_positive_rows"] == 18
    assert 0.0 <= r["metrics"]["core.roc_auc"]["estimate"] <= 1.0
    assert set(r["lead"]) == {"core", "beneish_fixed"}
