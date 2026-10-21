# Pre-registration of the holdout test (written before any holdout case was scored)

**Why.** The first 14 cases (the *development set*, `data/cases/cases.csv` at commit `82ba713`) were picked from memory of famous failures, and
I looked at their results while building the model. Any improvement measured on them would be contaminated. This note fixes, in advance, how a
**new, mechanically selected holdout set** will be used. It is committed and pushed before the holdout cases are evaluated, so its timestamp on
GitHub is the evidence that the rules were not changed afterwards.

## Holdout case discovery (mechanical; no outcome is looked at)

1. Scrape SEC's public **Accounting and Auditing Enforcement Release** list; keep releases dated 2012-01-01 or later whose *first respondent is a company*
   (name pattern; auditors, CPAs and individuals excluded).
2. Resolve the name to an EDGAR CIK by exact normalised match on a current or former registrant name.
3. Keep non-financial companies (SIC outside 6000-6799) that filed an **8-K Item 4.02** between 2010-06-01 and the AAER date.
4. The Item 4.02 text must name annual fiscal years, and at least one *original 10-K filed before the 4.02* must cover a named year with all required
   Beneish inputs (`controls.usable_years`). Misstated years are the named years that have such a 10-K.
5. Read the 4.02 snippet against the AAER title; exclude a pair only if it is clearly a different matter. Not in the development set.
6. **Every candidate that passes is included. None is dropped because of how the model scores it.**
7. Controls: the same deterministic rule as before (3 per case, nearest size, 3-digit then 2-digit SIC then division, no 4.02 in history).

## Frozen rules applied to the holdout

* **Baseline:** Beneish M-score flag if above -1.78.
* **Composite:** the `core` logistic regression (features and `C = 1` unchanged), **fitted on development-set rows only**, threshold = 90th percentile of the
  development controls' scores. No refit, no re-tuning, no feature changes on holdout data.
* **Primary hypothesis (H1):** the Beneish M-score ranks holdout misstated firm-years above holdout control firm-years, i.e. ROC-AUC greater than 0.5, judged by the
  lower end of a 95% company-level bootstrap interval.
* **Secondary:** composite ROC-AUC and PR-AUC; recall and false-positive rate at the frozen thresholds; cases flagged before the cut-off and lead time.
* Whatever the holdout shows is reported, including if it is worse than the development set.

## After the holdout test

* A pooled leave-one-company-out run on development + holdout gives the larger-sample headline (reported next to, not instead of, the holdout result).
* Sensitivity variants fixed now: TATA computed from income from continuing operations instead of net income.
* A universe base-rate check: share of all US non-financial 10-K filers that the M-score flags in fiscal 2015 and 2019 (XBRL `frames`), to test whether the
  matched controls' false-positive rate is representative.

## Deliberately not done

* **Quarterly (10-Q) signals:** labelled misstated periods are mostly annual and quarterly cash-flow items are year-to-date; a faithful implementation is a
  separate project.
* **Text signals** (MD&A language, auditor changes) are out of scope.
* **A public ranked list of current companies:** a model with precision this low at realistic base rates must not publish named accusations. Only aggregate rates are reported.
