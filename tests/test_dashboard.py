"""Smoke test: the Streamlit app renders every tab without raising."""

import pytest

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402

from redflag import config  # noqa: E402


def test_dashboard_renders_without_errors():
    at = AppTest.from_file(str(config.ROOT / "app" / "dashboard.py"), default_timeout=120).run()
    assert not at.exception, [e.value for e in at.exception]
    assert len(at.tabs) == 4
    assert any("not investment advice" in w.value.lower() for w in at.warning)


def test_dashboard_company_and_case_selection():
    at = AppTest.from_file(str(config.ROOT / "app" / "dashboard.py"), default_timeout=120).run()
    company = [s for s in at.selectbox if s.label == "Company"][0]
    company.select(company.options[3]).run()
    case = [s for s in at.selectbox if s.label == "Case"][0]
    case.select("MiMedx Group").run()
    assert not at.exception, [e.value for e in at.exception]
