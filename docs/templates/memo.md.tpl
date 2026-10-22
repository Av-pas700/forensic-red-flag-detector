# Memo: Can financial-statement red flags warn of restatements?

**To:** Audit and Risk Committee  **From:** Forensic Red-Flag Detector project  **Status:** screening study, not advice

*Flags indicate elevated risk worth investigating. They are not proof of fraud, are not investment advice, and many flagged companies will be honest.*

## 1. Question
If we had screened US companies' published accounts **before** a problem became public, how many of the companies that later restated or faced SEC
accounting action would we have flagged, how early, and at what cost in false alarms?

## 2. Method
* **Cases:** {{n_cases}} US non-financial companies, each with an SEC Form 8-K "non-reliance on previously issued financial statements" (Item 4.02) and an
  SEC accounting-enforcement release, checked against the filings themselves. **{{d_n_cases}} development cases** were chosen from memory and used to build the models;
  **{{h_n_cases}} holdout cases** were selected mechanically from SEC's enforcement list under rules published on GitHub before they were scored, and
  were scored with rules frozen on the development cases.
* **Peers:** {{n_controls}} healthy companies matched on industry, size and fiscal year, with no Item 4.02 filing in their history.
* **Tests:** the Beneish M-score (eight accounting ratios), accruals quality, receivables versus revenue growth, earnings versus operating cash flow, a Benford
  first-digit test, and a small logistic-regression composite.
* **No hindsight:** each year's numbers come only from that year's original 10-K; a case company's filings stop at its restatement notice (or an earlier verified public signal).
  Every company is scored by a model that never saw it.

## 3. Findings
{{table_generalisation}}

* **The result did not survive the holdout.** On the development cases the M-score looked modest but useful (ROC-AUC {{d_auc_beneish_fixed_full}}); on the untouched holdout it scored
  {{h_auc_beneish_fixed_full}}, flagging {{h_det_beneish_fixed}} holdout cases. {{h_reading}} Pooled over all {{n_cases}} cases the ROC-AUC is {{auc_beneish_fixed_full}}.
* **The refitted composite added nothing.** {{verdict_core}} The extra accruals, cash-flow and Benford tests did no better than chance individually (best other single test, {{best_other_name}}: ROC-AUC {{best_other_pt}}).
* **Exploratory, not a finding:** after seeing the holdout I split cases by restatement type. For revenue/receivable-type cases ({{bt_rev_cases}} cases) the M-score's ROC-AUC is {{bt_rev_auc}};
  for the other types ({{bt_oth_cases}} cases: tax, reserves, segment reporting, purchase accounting) it is {{bt_oth_auc}}. {{bt_reading}}
* **False alarms are the bigger problem.** The M-score flagged {{u_flag_2015}} of {{u_n_2015}} US filers in 2015 and {{u_flag_2019}} of {{u_n_2019}} in 2019, well above the {{fpr_beneish_fixed}} among matched controls. If 1% of
  companies were affected, a flag would be right only about {{ppv_univ_1_2015}} to {{ppv_univ_1_2019}} of the time.

## 4. Limitations
{{n_cases}} cases from few independent companies give wide intervals. Development cases were picked with hindsight from famous failures; holdout cases are mechanical but only cover companies that
appear in SEC accounting releases and had electronic (XBRL) data. Peers are not certified clean. Labels come from the years named in the 8-K and SEC order, which may not match what the numbers
show. Only annual accounts were tested; pre-2009 cases such as Enron are out of scope.

## 5. Recommendation
1. **Do not use the M-score, or the composite built here, as a stand-alone screen.** On evidence the model has not seen, it did not rank misstated filings above peers, and its false-alarm rate on ordinary companies is high.
2. If used at all, treat it as a narrow triage input for **revenue and receivables risk**, always followed by a human read of revenue-recognition notes, receivables ageing, auditor changes and late filings.
3. **Test the revenue-specific hypothesis properly:** fix the rule now, apply it to the next filing season and to a fresh, pre-registered sample of revenue-type restatements, and review realised precision against the real base rate before any resourcing decision.
4. Treat any list produced as confidential and as a prompt for questions, never as a finding about a named company.
