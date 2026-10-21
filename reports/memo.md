# Memo: Can financial-statement red flags warn of restatements?

**To:** Audit and Risk Committee  **From:** Forensic Red-Flag Detector project  **Status:** screening study, not advice

*Flags indicate elevated risk worth investigating. They are not proof of fraud, are not investment advice, and several flagged
companies will be honest.*

## 1. Question
If we had screened US companies' published accounts **before** a problem became public, how many of the companies that later restated
or faced SEC accounting action would we have flagged, how early, and at what cost in false alarms?

## 2. Method
* **Cases:** 14 US non-financial companies, each with an SEC Form 8-K "non-reliance on previously issued financial statements"
  (Item 4.02) and an SEC enforcement action on the public record (6 later also entered Chapter 11), checked against the filings themselves.
* **Peers:** 41 healthy companies matched on industry, size and fiscal year with no Item 4.02 filing in their history.
* **Tests:** the Beneish M-score (eight accounting ratios), accruals quality, receivables growth versus revenue growth, earnings versus
  operating cash flow, and a Benford first-digit test; plus a small logistic-regression composite.
* **No hindsight:** each year's numbers come only from that year's original 10-K, and a case company's filings stop at the earlier of its
  restatement notice and any earlier verified public signal.
* **Honest scoring:** every company is scored by a model that never saw it (leave-one-company-out); intervals come from resampling companies.

## 3. Findings
| Model | ROC-AUC [95% CI] | PR-AUC [95% CI] | Recall (misstated 10-Ks) | False-positive rate (control 10-Ks) | Cases flagged pre-event |
|---|---|---|---|---|---|
| Beneish M-score > -1.78 (baseline) | 0.70 [0.59, 0.80] | 0.51 [0.36, 0.69] | 41% | 9% | 8 of 14 |
| Composite, 6 signals (pre-specified) | 0.68 [0.55, 0.81] | 0.44 [0.33, 0.64] | 30% | 10% | 7 of 14 |
| Composite + Benford + NI-CFO gap | 0.65 [0.54, 0.77] | 0.40 [0.29, 0.61] | 30% | 13% | 6 of 14 |
| M-score + 3 signals (post hoc, exploratory) | 0.61 [0.48, 0.74] | 0.42 [0.30, 0.59] | 33% | 12% | 8 of 14 |

* The established M-score (flag above -1.78) is the best performer: 8 of 14 cases were flagged on at least one
  misstated-year 10-K before the restatement, a median of 0.98 years (4 quarters) earlier, at a
  9% false-positive rate on peers. It caught 41% of misstated company-years (interval 22% to 56%).
* The pre-specified composite was statistically indistinguishable from the published baseline (ROC-AUC difference -0.02, 95% CI -0.09 to 0.06). The extra accruals, cash-flow and Benford tests added nothing reliable: the best single test other than the M-score (sgi) had a
  ROC-AUC of 0.62 (95% CI 0.41 to 0.83), no better than chance given its interval, and Benford's law did not separate the groups.
* **Base-rate warning.** In this sample 26% of firm-years are misstated. If only 1% of companies were affected, the same flag rule would be right
  about 4.3% of the time (5%: 19.1%): most flags would be false alarms.

**Case by case** (lead = years from the earliest flagged misstated-year 10-K to the cut-off):

| Case | Misstated 10-Ks scored | Item 4.02 filed | Beneish flag: lead (yrs) | Composite flag: lead (yrs) |
|---|---|---|---|---|
| Stein Mart | 1 | 2012-11-09 | not flagged | not flagged |
| KIT digital | 1 | 2012-11-21 | 0.6 | 0.6 |
| UniTek Global Services | 1 | 2013-04-12 | not flagged | not flagged |
| Osiris Therapeutics | 1 | 2016-03-15 | 0.7 | 0.7 |
| Valeant Pharmaceuticals | 1 | 2016-03-21 | not flagged | not flagged |
| Roadrunner Transportation Systems | 2 | 2017-01-30 | not flagged | not flagged |
| Celadon Group | 1 | 2017-05-01 | 0.6 | 0.6 |
| Synchronoss Technologies | 2 | 2017-06-13 | not flagged | not flagged |
| MiMedx Group | 5 | 2018-06-07 | 5.0 | 5.0 |
| Quantum Corp | 3 | 2018-09-14 | 1.3 | 1.3 |
| Super Micro Computer | 2 | 2018-11-15 | 3.2 | not flagged |
| Kraft Heinz | 2 | 2019-05-06 | not flagged | not flagged |
| SAExploration Holdings | 4 | 2019-08-16 | 2.4 | 2.4 |
| Pareteum | 1 | 2019-10-21 | 0.6 | 0.6 |

## 4. Limitations
14 cases and few independent companies mean wide intervals and results that depend on which cases are included. Cases were chosen with hindsight from
well-known failures that also had electronic (XBRL) data, so any detector looks better than it would prospectively. Peers are not certified clean. Only annual
accounts were tested, pre-2009 cases such as Enron are out of scope, and different kinds of restatement (tax, leases, inventory) leave different footprints.

## 5. Recommendation
1. **Use the M-score as one low-cost triage input, not a verdict.** Pair a flag with a human read of revenue-recognition notes, receivables ageing,
   auditor changes and late filings before any escalation.
2. **Do not adopt the refitted composite or Benford tests** on this evidence; they add complexity without measured benefit.
3. **Pilot prospectively:** fix the rule now, apply it to the next filing season, log outcomes, and review realised precision against the real base rate
   before any wider use or resourcing decision.
4. Treat any list produced as confidential and as a prompt for questions, never as a finding about a named company.
