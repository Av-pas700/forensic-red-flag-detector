import json

import pandas as pd
import pytest

from redflag import config
from redflag.report import (
    count_tests,
    narrative_guards,
    render,
    render_all,
    stray_decimals,
)


@pytest.fixture(scope="module")
def results() -> dict:
    return json.loads((config.REPORTS / "results.json").read_text())


def test_unknown_placeholder_fails_loudly():
    with pytest.raises(KeyError, match="nope"):
        render("value: {{nope}}", {"yes": "1"})


def test_render_substitutes_placeholders():
    assert render("AUC {{a}} / {{ b }}", {"a": "0.70", "b": "x"}) == "AUC 0.70 / x"


def test_templates_must_not_contain_hand_typed_decimals():
    assert stray_decimals("AUC was 0.73 here") == ["0.73"]
    assert stray_decimals("```\nx = 0.5\n```\nplain {{a}} text, Item 4.02") == []


def test_committed_templates_are_free_of_hand_typed_decimals():
    for tpl in (config.ROOT / "docs" / "templates").glob("*.tpl"):
        assert stray_decimals(tpl.read_text()) == [], tpl.name


def test_narrative_guards_pass_for_committed_results(results):
    assert narrative_guards(results) == []


def test_narrative_guard_trips_if_composite_beats_baseline(results):
    rigged = json.loads(json.dumps(results))
    rigged["metrics"]["diff_auc.core_minus_beneish"] = {"estimate": 0.2, "lo": 0.1, "hi": 0.3}
    assert any("did not improve" in msg for msg in narrative_guards(rigged))


def test_count_tests_finds_this_suite():
    assert count_tests() >= 30


def test_documents_on_disk_match_a_fresh_render():
    for path, text in render_all(config.ROOT).items():
        assert path.read_text() == text, f"{path.name} is stale: run `make reproduce`"


def test_every_case_in_the_report_has_primary_sources():
    cases = pd.read_csv(config.DATA_PROCESSED / "cases_verified.csv")
    assert cases["nonreliance_url"].str.startswith("https://www.sec.gov/Archives/edgar/data/").all()
    assert cases["enforcement_url"].str.startswith("https://www.sec.gov/").all()
