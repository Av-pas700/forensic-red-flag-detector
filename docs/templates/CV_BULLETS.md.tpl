# CV bullets

All figures are produced by this repository's code (`reports/results.json`); `scripts/check_claims.py` verifies them.

* Built an end-to-end forensic-accounting screen in Python (pandas, NumPy, scikit-learn) on SEC EDGAR XBRL data - Beneish M-score, accruals, cash-flow-divergence and Benford tests written from scratch with point-in-time 10-K extraction to prevent look-ahead, {{n_tests}} unit tests and CI.
* Back-tested it on {{n_cases}} verified US restatement and SEC-enforcement cases against {{n_controls}} matched peers ({{n_pos}} misstated and {{n_neg}} control firm-years) with leave-one-company-out validation and company-level bootstrap CIs; the pooled M-score ROC-AUC was {{auc_beneish_fixed_pt}} (95% CI {{auc_beneish_fixed_lo}}-{{auc_beneish_fixed_hi}}).
* Pre-registered a holdout of {{h_n_cases}} mechanically selected SEC-enforcement cases on GitHub before scoring them; the M-score's ROC-AUC fell from {{d_auc_beneish_fixed_pt}} on development cases to {{h_auc_beneish_fixed_pt}} out of sample (95% CI {{h_auc_beneish_fixed_lo}}-{{h_auc_beneish_fixed_hi}}), and I reported the failure to generalise in a two-page audit-committee memo rather than the flattering in-sample number.
* Scored {{u_n_2015}} (2015) and {{u_n_2019}} (2019) US filers via the XBRL frames API: the M-score flags {{u_range}} of ordinary companies, implying a precision of only {{ppv_univ_range}} at a 1% base rate.

## Compact version (4 lines, for a one-page CV)

* Built a Python forensic-accounting screen (Beneish M-score, accruals, Benford) on SEC EDGAR XBRL data for {{n_cases}} verified restatement/SEC-enforcement cases and {{n_controls}} matched peers ({{n_pos}} + {{n_neg}} firm-years), with {{n_tests}} tests and CI.
* Validated with leave-one-company-out CV and bootstrap CIs: M-score ROC-AUC {{auc_beneish_fixed_pt}} (95% CI {{auc_beneish_fixed_lo}}-{{auc_beneish_fixed_hi}}); a refitted logistic composite was no better (AUC difference {{diff_core_pt}}, CI {{diff_core_lo}} to {{diff_core_hi}}).
* Pre-registered a {{h_n_cases}}-case holdout on GitHub before scoring: ROC-AUC fell from {{d_auc_beneish_fixed_pt}} (development) to {{h_auc_beneish_fixed_pt}} (95% CI {{h_auc_beneish_fixed_lo}}-{{h_auc_beneish_fixed_hi}}), and I reported "does not generalise" in a 2-page audit-committee memo.
* Scored {{u_n_2015}} (2015) and {{u_n_2019}} (2019) US filers via XBRL frames: the M-score flags {{u_range_dash}} of ordinary firms, implying {{ppv_univ_range}} precision at a 1% base rate.
