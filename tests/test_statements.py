"""Point-in-time extraction: a later restatement must never leak into an earlier year's numbers."""

import pandas as pd

from redflag.statements import extract_annual_statements


def _fact(val, end, accn, filed, form="10-K", start=None):
    row = {"val": val, "end": end, "accn": accn, "filed": filed, "form": form, "fy": 0, "fp": "FY"}
    if start:
        row["start"] = start
    return row


def synthetic_facts() -> dict:
    a, b, amend = "0001-14-000001", "0001-15-000001", "0001-15-000002"
    revenue = [
        # FY2013 10-K as originally filed
        _fact(1000, "2013-12-31", a, "2014-03-01", start="2013-01-01"),
        _fact(900, "2012-12-31", a, "2014-03-01", start="2012-01-01"),
        # FY2014 10-K restates FY2013 revenue to 950
        _fact(1100, "2014-12-31", b, "2015-03-01", start="2014-01-01"),
        _fact(950, "2013-12-31", b, "2015-03-01", start="2013-01-01"),
        # an amendment filed later must be ignored entirely
        _fact(999, "2013-12-31", amend, "2015-06-01", form="10-K/A", start="2013-01-01"),
    ]
    assets = [
        _fact(5000, "2013-12-31", a, "2014-03-01"),
        _fact(4500, "2012-12-31", a, "2014-03-01"),
        _fact(6000, "2014-12-31", b, "2015-03-01"),
        _fact(5200, "2013-12-31", b, "2015-03-01"),
    ]
    return {
        "cik": 1,
        "facts": {
            "us-gaap": {
                "Revenues": {"units": {"USD": revenue}},
                "Assets": {"units": {"USD": assets}},
            }
        },
    }


def test_each_year_uses_only_its_own_filing():
    df = extract_annual_statements(synthetic_facts(), 1).set_index("fyear")
    assert df.loc[2013, "revenue"] == 1000 and df.loc[2013, "revenue_prev"] == 900
    # FY2014 sees the restated comparative; FY2013 must NOT
    assert df.loc[2014, "revenue"] == 1100 and df.loc[2014, "revenue_prev"] == 950
    assert df.loc[2013, "total_assets"] == 5000


def test_amendments_are_ignored():
    df = extract_annual_statements(synthetic_facts(), 1)
    assert len(df) == 2
    assert 999 not in df["revenue"].tolist() + df["revenue_prev"].tolist()


def test_filing_dates_and_fiscal_year_label():
    df = extract_annual_statements(synthetic_facts(), 1)
    assert pd.api.types.is_datetime64_any_dtype(df["filed"])
    assert df["filed"].tolist() == [pd.Timestamp("2014-03-01"), pd.Timestamp("2015-03-01")]
    assert df["fyear"].tolist() == [2013, 2014]


def test_january_year_end_belongs_to_prior_fiscal_year():
    facts = synthetic_facts()
    for tag in facts["facts"]["us-gaap"].values():
        for r in tag["units"]["USD"]:
            r["end"] = r["end"].replace("-12-31", "-01-31")
            if "start" in r:
                r["start"] = r["start"].replace("-01-01", "-02-01")
    df = extract_annual_statements(facts, 1)
    assert df["fyear"].tolist() == [2012, 2013]
