import numpy as np
import pandas as pd
import pytest

from redflag.features import (
    BENEISH_COEF,
    BENEISH_THRESHOLD,
    accrual_signals,
    beneish_indices,
    beneish_mscore,
    compute_features,
)


def test_indices_match_hand_calculation(example_row):
    idx = beneish_indices(example_row).iloc[0]
    assert idx["dsri"] == pytest.approx((180 / 1200) / (100 / 1000))  # 1.5
    assert idx["gmi"] == pytest.approx(0.4 / 0.375)  # 1.0667
    assert idx["aqi"] == pytest.approx((1 - 820 / 1200) / (1 - 700 / 1000))  # 1.0556
    assert idx["sgi"] == pytest.approx(1.2)
    assert idx["depi"] == pytest.approx(73 / 63)  # (50/350)/(45/365)
    assert idx["sgai"] == pytest.approx(1.25)
    assert idx["lvgi"] == pytest.approx(1.25)  # (600/1200)/(400/1000)
    assert idx["tata"] == pytest.approx(0.05)  # (120-60)/1200
    assert idx["n_imputed"] == 0


def test_mscore_matches_hand_calculation(example_row):
    # -4.84 + .920(1.5) + .528(1.06667) + .404(1.05556) + .892(1.2) + .115(1.15873)
    #       - .172(1.25) + 4.679(.05) - .327(1.25)  = -1.6565
    m = beneish_mscore(beneish_indices(example_row)).iloc[0]
    expected = (
        -4.84
        + 0.920 * 1.5
        + 0.528 * (0.4 / 0.375)
        + 0.404 * (0.38 / 1.2 / 0.3)
        + 0.892 * 1.2
        + 0.115 * (73 / 63)
        - 0.172 * 1.25
        + 4.679 * 0.05
        - 0.327 * 1.25
    )
    assert m == pytest.approx(expected)
    assert m == pytest.approx(-1.6565, abs=1e-4)
    assert m > BENEISH_THRESHOLD  # would be flagged at the conventional -1.78 cut-off


def test_neutral_row_scores_at_the_constant(example_row):
    flat = example_row.copy()
    for col in list(flat.columns):
        if col.endswith("_prev"):
            flat[col[:-5]] = flat[col]
    idx = beneish_indices(flat)
    # all ratio indices are 1 and TATA = (NI - CFO)/TA; force TATA to 0 via CFO = NI
    flat["cfo"] = flat["net_income"]
    m = beneish_mscore(beneish_indices(flat)).iloc[0]
    expected = BENEISH_COEF["const"] + sum(v for k, v in BENEISH_COEF.items() if k not in ("const", "tata"))
    assert m == pytest.approx(expected)
    assert idx.loc[0, ["dsri", "gmi", "aqi", "sgi", "depi", "sgai", "lvgi"]].eq(1).all()


def test_missing_optional_inputs_become_neutral_and_are_counted(example_row):
    row = example_row.copy()
    row[["cogs", "cogs_prev", "sga", "sga_prev"]] = np.nan
    idx = beneish_indices(row).iloc[0]
    assert idx["gmi"] == 1.0 and idx["sgai"] == 1.0
    assert idx["n_imputed"] == 2


def test_missing_required_input_gives_nan_not_zero(example_row):
    row = example_row.copy()
    row["total_assets"] = np.nan
    assert np.isnan(beneish_mscore(beneish_indices(row)).iloc[0])


def test_zero_denominator_is_nan_not_inf(example_row):
    row = example_row.copy()
    row["revenue_prev"] = 0.0
    idx = beneish_indices(row).iloc[0]
    assert np.isnan(idx["sgi"]) and not np.isinf(idx["dsri"])


def test_accruals_and_cashflow_gap_hand_calculation(example_row):
    a = accrual_signals(example_row).iloc[0]
    avg_assets = (1200 + 1000) / 2
    assert a["total_accruals"] == pytest.approx((120 - 60) / avg_assets)
    # Sloan: (dCA - dCash) - (dCL - dDebtCurrent) - Dep = (100-20) - (100-10) - 45 = -55
    assert a["sloan_accruals"] == pytest.approx(-55 / avg_assets)
    assert a["ar_growth"] == pytest.approx(0.8)
    assert a["rev_growth"] == pytest.approx(0.2)
    assert a["ar_rev_gap"] == pytest.approx(0.6)
    assert a["ni_cfo_gap_rev"] == pytest.approx(60 / 1200)


def test_compute_features_flags_against_threshold(example_row):
    out = compute_features(example_row)
    assert bool(out.loc[0, "beneish_flag"]) is True
    assert out.loc[0, "mscore"] == pytest.approx(-1.6565, abs=1e-4)


def test_index_clipping_bounds_outliers(example_row):
    row = example_row.copy()
    row["receivables"] = 1e9
    assert beneish_indices(row).loc[0, "dsri"] == 10.0
    assert isinstance(row, pd.DataFrame)
