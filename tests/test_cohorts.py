"""Integrity of the development/holdout split and of the committed results."""

import json

import pandas as pd
import pytest

from redflag import config


@pytest.fixture(scope="module")
def cases() -> pd.DataFrame:
    return pd.read_csv(
        config.DATA_PROCESSED / "cases_verified.csv", parse_dates=["nonreliance_date", "enforcement_date"]
    )


@pytest.fixture(scope="module")
def results() -> dict:
    return json.loads((config.REPORTS / "results.json").read_text())


def test_cohort_labels_are_exhaustive_and_disjoint(cases):
    assert set(cases["cohort"]) == {"development", "holdout"}
    assert cases["cik"].is_unique and cases["case_id"].is_unique


def test_holdout_cases_come_from_the_aaer_index_with_a_verified_4_02(cases):
    aaer = pd.read_csv(config.DATA_CASES / "aaer_index.csv")
    hold = cases[cases["cohort"] == "holdout"]
    assert len(hold) >= 10
    assert hold["enforcement_note"].str.startswith("AAER-").all()
    nums = hold["enforcement_note"].str.extract(r"AAER-(\d+)")[0].astype(int)
    assert nums.isin(aaer["aaer_no"]).all()
    assert hold["nonreliance_url"].str.contains("/Archives/edgar/data/").all()
    assert (hold["nonreliance_date"] <= hold["enforcement_date"]).all()


def test_misstated_years_all_precede_the_event(cases):
    for _, c in cases.iterrows():
        years = [int(y) for y in str(c["positive_fyears"]).split(";")]
        assert max(years) <= c["nonreliance_date"].year


def test_every_case_has_an_issue_type(cases):
    assert cases["issue_type"].isin(["revenue", "other"]).all()


def test_preregistration_precedes_holdout_scoring_in_the_repo_docs():
    text = (config.ROOT / "docs" / "preregistration.md").read_text()
    assert "written before any holdout case was scored" in text.lower()
    assert "Addendum" in text  # post-hoc material is separated and labelled


def test_results_json_has_all_cohorts_and_sections(results):
    for key in ("development", "holdout", "universe", "by_issue_type", "sensitivity_ops"):
        assert key in results
    assert (
        results["holdout"]["n_cases"] + results["development"]["sample"]["n_cases"]
        == results["sample"]["n_cases"]
    )


def test_holdout_metrics_use_only_holdout_rows(results):
    h = results["holdout"]
    pooled = results["sample"]
    dev = results["development"]["sample"]
    assert h["n_positive_rows"] + dev["n_positive_rows"] == pooled["n_positive_rows"]
    assert h["n_negative_rows"] + dev["n_negative_rows"] == pooled["n_negative_rows"]


def test_universe_flag_rates_are_proportions(results):
    for year, d in results["universe"].items():
        assert 0 < d["flag_share"] < 1 and d["n_scored"] > 1000, year
