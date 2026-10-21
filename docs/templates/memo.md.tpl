# Memo: Can financial-statement red flags warn of restatements?

**To:** Audit and Risk Committee  **From:** Forensic Red-Flag Detector project  **Status:** screening study, not advice

*Flags indicate elevated risk worth investigating. They are not proof of fraud, are not investment advice, and several flagged
companies will be honest.*

## 1. Question
If we had screened US companies' published accounts **before** a problem became public, how many of the companies that later restated
or faced SEC accounting action would we have flagged, how early, and at what cost in false alarms?

## 2. Method
* **Cases:** {{n_cases}} US non-financial companies, each with an SEC Form 8-K "non-reliance on previously issued financial statements"
  (Item 4.02) and an SEC enforcement action on the public record ({{n_bankrupt}} later also entered Chapter 11), checked against the filings themselves.
* **Peers:** {{n_controls}} healthy companies matched on industry, size and fiscal year with no Item 4.02 filing in their history.
* **Tests:** the Beneish M-score (eight accounting ratios), accruals quality, receivables growth versus revenue growth, earnings versus
  operating cash flow, and a Benford first-digit test; plus a small logistic-regression composite.
* **No hindsight:** each year's numbers come only from that year's original 10-K, and a case company's filings stop at the earlier of its
  restatement notice and any earlier verified public signal.
* **Honest scoring:** every company is scored by a model that never saw it (leave-one-company-out); intervals come from resampling companies.

## 3. Findings
{{table_models}}

* The established M-score (flag above {{beneish_threshold}}) is the best performer: {{det_beneish_fixed}} cases were flagged on at least one
  misstated-year 10-K before the restatement, a median of {{lead_med_y_beneish_fixed}} years ({{lead_med_q_beneish_fixed}} quarters) earlier, at a
  {{fpr_beneish_fixed}} false-positive rate on peers. It caught {{rec_beneish_fixed}} of misstated company-years (interval {{rec_beneish_fixed_ci}}).
* {{verdict_core}} The extra accruals, cash-flow and Benford tests added nothing reliable: the best single test other than the M-score ({{best_other_name}}) had a
  ROC-AUC of {{best_other_pt}}, no better than chance given its interval, and Benford's law did not separate the groups.
* **Base-rate warning.** In this sample {{pr_prevalence}} of firm-years are misstated. If only 1% of companies were affected, the same flag rule would be right
  about {{ppv_beneish_fixed_1}} of the time (5%: {{ppv_beneish_fixed_5}}): most flags would be false alarms.

**Case by case** (lead = years from the earliest flagged misstated-year 10-K to the cut-off):

{{table_cases}}

## 4. Limitations
{{n_cases}} cases and few independent companies mean wide intervals and results that depend on which cases are included. Cases were chosen with hindsight from
well-known failures that also had electronic (XBRL) data, so any detector looks better than it would prospectively. Peers are not certified clean. Only annual
accounts were tested, pre-2009 cases such as Enron are out of scope, and different kinds of restatement (tax, leases, inventory) leave different footprints.

## 5. Recommendation
1. **Use the M-score as one low-cost triage input, not a verdict.** Pair a flag with a human read of revenue-recognition notes, receivables ageing,
   auditor changes and late filings before any escalation.
2. **Do not adopt the refitted composite or Benford tests** on this evidence; they add complexity without measured benefit.
3. **Pilot prospectively:** fix the rule now, apply it to the next filing season, log outcomes, and review realised precision against the real base rate
   before any wider use or resourcing decision.
4. Treat any list produced as confidential and as a prompt for questions, never as a finding about a named company.
