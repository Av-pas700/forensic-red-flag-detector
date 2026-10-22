# Memo: Can financial-statement red flags warn of restatements?

**To:** Audit and Risk Committee  **From:** Forensic Red-Flag Detector project  **Status:** screening study, not advice

*Flags indicate elevated risk worth investigating. They are not proof of fraud, are not investment advice, and many flagged companies will be honest.*

## 1. Question
If we had screened US companies' published accounts **before** a problem became public, how many of the companies that later restated or faced SEC
accounting action would we have flagged, how early, and at what cost in false alarms?

## 2. Method
* **Cases:** 27 US non-financial companies, each with an SEC Form 8-K "non-reliance on previously issued financial statements" (Item 4.02) and an
  SEC accounting-enforcement release, checked against the filings themselves. **14 development cases** were chosen from memory and used to build the models;
  **13 holdout cases** were selected mechanically from SEC's enforcement list under rules published on GitHub before they were scored, and
  were scored with rules frozen on the development cases.
* **Peers:** 80 healthy companies matched on industry, size and fiscal year, with no Item 4.02 filing in their history.
* **Tests:** the Beneish M-score (eight accounting ratios), accruals quality, receivables versus revenue growth, earnings versus operating cash flow, a Benford
  first-digit test, and a small logistic-regression composite.
* **No hindsight:** each year's numbers come only from that year's original 10-K; a case company's filings stop at its restatement notice (or an earlier verified public signal).
  Every company is scored by a model that never saw it.

## 3. Findings
| Model | Development cases (LOCO) | Holdout cases (frozen rules) | Pooled (LOCO) |
|---|---|---|---|
| Beneish M-score > -1.78: ROC-AUC [95% CI] | 0.70 [0.59, 0.80] | 0.49 [0.34, 0.63] | 0.61 [0.51, 0.70] |
| Composite, 6 signals: ROC-AUC [95% CI] | 0.68 [0.55, 0.81] | 0.48 [0.32, 0.63] | 0.55 [0.44, 0.67] |
| Beneish M-score > -1.78: recall / false-positive rate | 41% / 9% | 10% / 5% | 28% / 7% |
| Beneish M-score > -1.78: cases flagged before cut-off | 8 of 14 | 2 of 13 | 10 of 27 |
| Composite, 6 signals: recall / false-positive rate | 30% / 10% | 5% / 5% | 21% / 12% |
| Composite, 6 signals: cases flagged before cut-off | 7 of 14 | 1 of 13 | 8 of 27 |

* **The result did not survive the holdout.** On the development cases the M-score looked modest but useful (ROC-AUC 0.70 (95% CI 0.59 to 0.80)); on the untouched holdout it scored
  0.49 (95% CI 0.34 to 0.63), flagging 2 of 13 holdout cases. The M-score did no better than chance on unseen cases, so the development result did not generalise. Pooled over all 27 cases the ROC-AUC is 0.61 (95% CI 0.51 to 0.70).
* **The refitted composite added nothing.** The pre-specified composite was statistically indistinguishable from the published baseline (ROC-AUC difference -0.06, 95% CI -0.17 to 0.06). The extra accruals, cash-flow and Benford tests did no better than chance individually (best other single test, sgi: ROC-AUC 0.58 (95% CI 0.42 to 0.73)).
* **Exploratory, not a finding:** after seeing the holdout I split cases by restatement type. For revenue/receivable-type cases (15 cases) the M-score's ROC-AUC is 0.67 (95% CI 0.54 to 0.79);
  for the other types (12 cases: tax, reserves, segment reporting, purchase accounting) it is 0.54 (95% CI 0.38 to 0.67). The M-score separates revenue-type cases from controls but not the others - consistent with it being built for revenue and receivable manipulation. The two intervals overlap, the grouping was made after I saw the holdout result, and the cell sizes are small, so this is a hypothesis for a pre-registered follow-up, not a finding.
* **False alarms are the bigger problem.** The M-score flagged 12% of 2,777 US filers in 2015 and 19% of 2,502 in 2019, well above the 7% among matched controls. If 1% of
  companies were affected, a flag would be right only about 2.3% to 1.5% of the time.

## 4. Limitations
27 cases from few independent companies give wide intervals. Development cases were picked with hindsight from famous failures; holdout cases are mechanical but only cover companies that
appear in SEC accounting releases and had electronic (XBRL) data. Peers are not certified clean. Labels come from the years named in the 8-K and SEC order, which may not match what the numbers
show. Only annual accounts were tested; pre-2009 cases such as Enron are out of scope.

## 5. Recommendation
1. **Do not use the M-score, or the composite built here, as a stand-alone screen.** On evidence the model has not seen, it did not rank misstated filings above peers, and its false-alarm rate on ordinary companies is high.
2. If used at all, treat it as a narrow triage input for **revenue and receivables risk**, always followed by a human read of revenue-recognition notes, receivables ageing, auditor changes and late filings.
3. **Test the revenue-specific hypothesis properly:** fix the rule now, apply it to the next filing season and to a fresh, pre-registered sample of revenue-type restatements, and review realised precision against the real base rate before any resourcing decision.
4. Treat any list produced as confidential and as a prompt for questions, never as a finding about a named company.
