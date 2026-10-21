import pytest

from redflag import config

pypdf = pytest.importorskip("pypdf")


def test_memo_pdf_is_at_most_two_pages_if_built():
    pdf = config.REPORTS / "memo.pdf"
    if not pdf.exists():
        pytest.skip("memo.pdf not built (needs Chrome; run `make reproduce`)")
    assert len(pypdf.PdfReader(str(pdf)).pages) <= 2


def test_memo_has_required_sections():
    text = (config.REPORTS / "memo.md").read_text()
    for heading in (
        "## 1. Question",
        "## 2. Method",
        "## 3. Findings",
        "## 4. Limitations",
        "## 5. Recommendation",
    ):
        assert heading in text
    assert "not investment advice" in text.lower()
    assert len(text.split()) < 1000  # two pages of plain English (the PDF page-count test is the real gate)
