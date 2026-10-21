# CV bullets

All figures are produced by this repository's code (`reports/results.json`); `scripts/check_claims.py` verifies them.

* Built an end-to-end forensic-accounting screen in Python (pandas, NumPy, scikit-learn) from SEC EDGAR XBRL data - Beneish M-score, accruals quality,
  cash-flow divergence and Benford tests implemented from scratch with point-in-time 10-K extraction to prevent look-ahead leakage, backed by 60 unit tests and CI (pytest, ruff).
* Back-tested the screen on 14 verified US restatement and SEC-enforcement cases against 41 matched peers using leave-one-company-out
  validation and company-level bootstrap intervals: the Beneish baseline reached ROC-AUC 0.70 (95% CI 0.59-0.80), flagged 8 of 14 cases a median 0.98 years before the restatement at a 9% false-positive rate, and a refitted composite model did not improve on it.
* Reported the weak and the strong results plainly in a two-page audit-committee memo and a Streamlit dashboard (ranked watchlist, score breakdown, case-study timelines), including a base-rate analysis showing implied precision of 4.3% at a 1% prevalence.
