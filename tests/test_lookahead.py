"""No case-company filing on/after its cut-off may reach scoring or evaluation."""

import pandas as pd
import pytest

from redflag.validation import assert_no_lookahead, build_panel


def _fin(cik, fyears, filed_year_offset=1):
    rows = []
    for fy in fyears:
        rows.append(
            {
                "cik": cik,
                "accn": f"a{cik}{fy}",
                "filed": f"{fy + filed_year_offset}-03-01",
                "fye": f"{fy}-12-31",
                "fye_prev": f"{fy - 1}-12-31",
                "fyear": fy,
                "revenue": 1200.0,
                "revenue_prev": 1000.0,
                "cogs": 700.0,
                "cogs_prev": 600.0,
                "sga": 100.0,
                "sga_prev": 90.0,
                "dep": 40.0,
                "dep_prev": 38.0,
                "net_income": 100.0,
                "cfo": 80.0,
                "receivables": 150.0,
                "receivables_prev": 120.0,
                "current_assets": 500.0,
                "current_assets_prev": 450.0,
                "ppe": 300.0,
                "ppe_prev": 280.0,
                "total_assets": 1500.0,
                "total_assets_prev": 1400.0,
                "current_liabilities": 300.0,
                "current_liabilities_prev": 280.0,
                "lt_debt": 200.0,
                "lt_debt_prev": 190.0,
                "cash": 50.0,
                "cash_prev": 40.0,
                "debt_current": 10.0,
                "debt_current_prev": 9.0,
                **{f"bd{d}": 10 for d in range(1, 10)},
            }
        )
    return pd.DataFrame(rows)


@pytest.fixture
def setup():
    fin = pd.concat([_fin(1, [2011, 2012, 2013, 2014, 2015]), _fin(2, [2012, 2013, 2014])])
    companies = pd.DataFrame(
        [
            {"cik": 1, "name": "Case Co", "role": "case", "case_id": "c", "sic": 7372},
            {"cik": 2, "name": "Ctrl Co", "role": "control", "case_id": "c", "sic": 7372},
        ]
    )
    cases = pd.DataFrame(
        [
            {
                "case_id": "c",
                "cik": 1,
                "company": "Case Co",
                "positive_fyears": [2012, 2013],
                "nonreliance_date": pd.Timestamp("2015-06-01"),
                "first_signal_date": pd.NaT,
                "cutoff": pd.Timestamp("2015-06-01"),
            }
        ]
    )
    return fin, companies, cases


def test_filings_at_or_after_cutoff_are_dropped(setup):
    fin, companies, cases = setup
    panel = build_panel(fin, companies, cases)
    case_rows = panel[panel["role"] == "case"]
    # FY2015 10-K is filed 2016-03-01, after the 2015-06-01 cut-off -> gone; FY2014 (filed 2015-03) stays
    assert case_rows["fyear"].max() == 2014
    assert (case_rows["filed"] < pd.Timestamp("2015-06-01")).all()
    assert_no_lookahead(panel, cases)


def test_labels_follow_the_misstated_years_only(setup):
    fin, companies, cases = setup
    panel = build_panel(fin, companies, cases)
    case_labels = panel[panel["role"] == "case"].set_index("fyear")["label"]
    assert case_labels.loc[2012] == 1 and case_labels.loc[2013] == 1
    assert pd.isna(case_labels.loc[2011]) and pd.isna(case_labels.loc[2014])
    ctrl = panel[panel["role"] == "control"].set_index("fyear")["label"]
    assert ctrl.loc[2012] == 0 and ctrl.loc[2013] == 0 and pd.isna(ctrl.loc[2014])


def test_guard_raises_if_a_late_filing_sneaks_in(setup):
    fin, companies, cases = setup
    panel = build_panel(fin, companies, cases)
    leaked = pd.concat(
        [panel, panel[panel["role"] == "case"].head(1).assign(filed=pd.Timestamp("2016-03-01"))]
    )
    with pytest.raises(AssertionError, match="look-ahead"):
        assert_no_lookahead(leaked, cases)


def test_earlier_first_signal_tightens_the_cutoff(setup):
    fin, companies, cases = setup
    cases = cases.assign(first_signal_date=pd.Timestamp("2014-01-01"), cutoff=pd.Timestamp("2014-01-01"))
    panel = build_panel(fin, companies, cases)
    assert panel[panel["role"] == "case"]["fyear"].max() == 2012  # FY2013 10-K filed 2014-03 is after
