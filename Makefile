PY ?= python

.PHONY: install data reproduce test lint dashboard clean

install:
	$(PY) -m pip install -e ".[dev,app,report]"

# Rebuild data/processed from the SEC (needs SEC_USER_AGENT; slow the first time, then cached).
data:
	$(PY) scripts/build_dataset.py

# Everything that regenerates results, figures and documents from the committed dataset (offline).
reproduce:
	$(PY) scripts/run_analysis.py
	$(PY) scripts/render_docs.py
	$(PY) scripts/build_memo_pdf.py
	$(PY) scripts/check_claims.py

test:
	$(PY) -m pytest

lint:
	$(PY) -m ruff check .

dashboard:
	$(PY) -m streamlit run app/dashboard.py

clean:
	rm -rf reports/figures reports/tables reports/results.json .pytest_cache .ruff_cache
