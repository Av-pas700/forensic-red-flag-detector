"""Pins the three hand-checked ratios in docs/verification.md to the committed dataset."""

import pandas as pd
import pytest

from redflag import config
from redflag.features import beneish_indices


@pytest.fixture(scope="module")
def fin() -> pd.DataFrame:
    return pd.read_csv(config.DATA_PROCESSED / "financials.csv")


def _row(fin: pd.DataFrame, accn: str) -> pd.DataFrame:
    row = fin[fin["accn"] == accn]
    assert len(row) == 1, f"{accn} missing from data/processed/financials.csv"
    return row


def test_synchronoss_fy2016_dsri(fin):
    row = _row(fin, "0001131554-17-000037")
    assert row.iloc[0][["receivables", "receivables_prev", "revenue", "revenue_prev"]].tolist() == [
        137_233_000,
        136_117_000,
        476_750_000,
        428_117_000,
    ]
    assert beneish_indices(row).iloc[0]["dsri"] == pytest.approx((137_233 / 476_750) / (136_117 / 428_117))
    assert beneish_indices(row).iloc[0]["dsri"] == pytest.approx(0.9054, abs=5e-5)


def test_mimedx_fy2015_sgi_gmi(fin):
    row = _row(fin, "0001376339-16-000138")
    idx = beneish_indices(row).iloc[0]
    assert idx["sgi"] == pytest.approx(187_296 / 118_223)
    assert idx["gmi"] == pytest.approx((105_558 / 118_223) / (167_094 / 187_296))
    assert (idx["sgi"], idx["gmi"]) == (pytest.approx(1.5843, abs=5e-5), pytest.approx(1.0008, abs=5e-5))


def test_kraft_heinz_fy2017_tata(fin):
    row = _row(fin, "0001637459-18-000015")
    assert row.iloc[0]["tag_net_income"] == "ProfitLoss"  # consolidated income, like-for-like with CFO
    assert beneish_indices(row).iloc[0]["tata"] == pytest.approx((10_990 - 527) / 120_232)
    assert beneish_indices(row).iloc[0]["tata"] == pytest.approx(0.0870, abs=5e-5)
