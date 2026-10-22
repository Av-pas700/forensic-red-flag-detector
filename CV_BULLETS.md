# CV bullets

All figures are produced by this repository's code (`reports/results.json`); `scripts/check_claims.py` verifies them.

* Built an end-to-end forensic-accounting screen in Python (pandas, NumPy, scikit-learn) on SEC EDGAR XBRL data - Beneish M-score, accruals, cash-flow-divergence and Benford tests written from scratch with point-in-time 10-K extraction to prevent look-ahead, 72 unit tests and CI.
* Back-tested it on 27 verified US restatement and SEC-enforcement cases against 80 matched peers (47 misstated and 137 control firm-years) with leave-one-company-out validation and company-level bootstrap CIs; the pooled M-score ROC-AUC was 0.61 (95% CI 0.51-0.70).
* Pre-registered a holdout of 13 mechanically selected SEC-enforcement cases on GitHub before scoring them; the M-score's ROC-AUC fell from 0.70 on development cases to 0.49 out of sample (95% CI 0.34-0.63), and I reported the failure to generalise in a two-page audit-committee memo rather than the flattering in-sample number.
* Scored 2,777 (2015) and 2,502 (2019) US filers via the XBRL frames API: the M-score flags 12% to 19% of ordinary companies, implying a precision of only 1.5%-2.3% at a 1% base rate.

## Compact version (4 lines, for a one-page CV)

* Built a Python forensic-accounting screen (Beneish M-score, accruals, Benford) on SEC EDGAR XBRL data for 27 verified restatement/SEC-enforcement cases and 80 matched peers (47 + 137 firm-years), with 72 tests and CI.
* Validated with leave-one-company-out CV and bootstrap CIs: M-score ROC-AUC 0.61 (95% CI 0.51-0.70); a refitted logistic composite was no better (AUC difference -0.06, CI -0.17 to 0.06).
* Pre-registered a 13-case holdout on GitHub before scoring: ROC-AUC fell from 0.70 (development) to 0.49 (95% CI 0.34-0.63), and I reported "does not generalise" in a 2-page audit-committee memo.
* Scored 2,777 (2015) and 2,502 (2019) US filers via XBRL frames: the M-score flags 12%-19% of ordinary firms, implying 1.5%-2.3% precision at a 1% base rate.
