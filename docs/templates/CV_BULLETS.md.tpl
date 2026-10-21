# CV bullets

All figures are produced by this repository's code (`reports/results.json`); `scripts/check_claims.py` verifies them.

* Built an end-to-end forensic-accounting screen in Python (pandas, NumPy, scikit-learn) from SEC EDGAR XBRL data - Beneish M-score, accruals quality,
  cash-flow divergence and Benford tests implemented from scratch with point-in-time 10-K extraction to prevent look-ahead leakage, backed by {{n_tests}} unit tests and CI (pytest, ruff).
* Back-tested the screen on {{n_cases}} verified US restatement and SEC-enforcement cases against {{n_controls}} matched peers using leave-one-company-out
  validation and company-level bootstrap intervals: the Beneish baseline reached ROC-AUC {{auc_beneish_fixed_pt}} (95% CI {{auc_beneish_fixed_lo}}-{{auc_beneish_fixed_hi}}), flagged {{det_beneish_fixed}} cases a median {{lead_med_y_beneish_fixed}} years before the restatement at a {{fpr_beneish_fixed}} false-positive rate, and a refitted composite model did not improve on it.
* Reported the weak and the strong results plainly in a two-page audit-committee memo and a Streamlit dashboard (ranked watchlist, score breakdown, case-study timelines), including a base-rate analysis showing implied precision of {{ppv_beneish_fixed_1}} at a 1% prevalence.
