# Methods

All signals are *screening* signals: they rank filings by how much they resemble the filings of companies
that later disclosed accounting problems. They do not establish intent, and a flag is a prompt to read the
filing, not a conclusion.

## 1. Data and point-in-time construction

* Source: SEC EDGAR XBRL `companyfacts`, `submissions` and `frames` APIs (free; a `User-Agent` identifying the
  requester is mandatory and is read from `SEC_USER_AGENT`). Requests are throttled to 8 per second (SEC limit: 10).
* Only original **10-K** filings are used. 10-K/A amendments are ignored because they are published after the fact.
* `companyfacts` serves every value ever reported for a period, including numbers **restated in later filings**.
  Using those would leak the future into a "before the restatement" test. Each fiscal year is therefore built only
  from facts carrying the accession number of **that year's own 10-K**: the current-year column and the prior-year
  comparative column exactly as the company presented them on the filing date.
* XBRL starts around 2009 (large filers) and 2011 (smaller filers), so classic cases such as Enron or WorldCom are out
  of scope, and some otherwise attractive cases (see `docs/case_selection.md`) had to be dropped because the
  misstated 10-K pre-dates the company's XBRL.
* Financial companies (SIC 6000-6799) are excluded: Beneish's model was fitted on non-financial firms.
* Fiscal-year label: year of the fiscal year-end, except year-ends in January/February which belong to the prior year.

## 2. Beneish (1999) M-score

```
M = -4.84 + 0.920*DSRI + 0.528*GMI + 0.404*AQI + 0.892*SGI + 0.115*DEPI - 0.172*SGAI + 4.679*TATA - 0.327*LVGI
```

| Index | Definition (t = current year, t-1 = prior year, both as shown in the same 10-K) |
|---|---|
| DSRI | (Receivables/Sales)_t / (Receivables/Sales)_t-1 |
| GMI | GrossMargin_t-1 / GrossMargin_t |
| AQI | [1 - (CurrentAssets + PP&E)/TotalAssets]_t / same_t-1 |
| SGI | Sales_t / Sales_t-1 |
| DEPI | [Dep/(Dep+PP&E)]_t-1 / [Dep/(Dep+PP&E)]_t |
| SGAI | (SG&A/Sales)_t / (SG&A/Sales)_t-1 |
| LVGI | [(CurrentLiabilities + LongTermDebt)/TotalAssets]_t / same_t-1 |
| TATA | (Net income - Operating cash flow)/TotalAssets_t  (the cash-flow form of total accruals) |

**Threshold.** An M-score above **-1.78** is the cut-off most often used in practice and is the baseline here. It is a
convention, not a law: the right cut-off depends on the assumed relative cost of missing a manipulator versus
investigating an honest firm, and on the base rate.

**Known limitations.** Fitted on 1982-1992 US manufacturing and retail firms; weak on firms with unclassified balance
sheets, no trade receivables (retailers), negative gross margins, or heavy M&A (acquisitions inflate SGI/AQI/TATA
without any manipulation); sensitive to a single near-zero denominator; the published version was estimated on
*earnings-overstatement* cases and says little about other kinds of restatement (tax, lease, classification).

**Fixed (not data-driven) bounds.** Indices are clipped to [0, 10] and TATA to [-1, 1] so one near-zero denominator
cannot dominate. If an optional input is absent (COGS, SG&A, depreciation, trade receivables on both dates) the index
takes the neutral value 1 and `n_imputed` is incremented; missing long-term debt is read as zero. Firm-years with more
than 2 substitutions, or with a required input missing, are dropped (and logged when a whole case is lost).

## 3. Accruals quality

* **Total accruals / average assets** = (Net income - CFO) / mean(Assets_t, Assets_t-1).
* **Sloan (1996)-style balance-sheet accruals** = [(dCA - dCash) - (dCL - dDebtCurrent) - Depreciation] / mean assets.
  The income-tax-payable adjustment of the original is omitted because the tag is sparse.
  Sloan's finding is that high-accrual earnings are less persistent; extreme accruals are a standard manipulation proxy.

## 4. Cash-flow divergence

* **Receivables growth minus revenue growth** (clipped to [-2, 2]): receivables outrunning sales is the classic footprint
  of revenue booked but not collected.
* **(Net income - operating cash flow) / revenue**: earnings not backed by cash per dollar of sales. It overlaps TATA by
  construction; both are reported, and the pre-specified core composite uses only TATA.

## 5. Benford first-digit test

Expected share of leading digit d is `log10(1 + 1/d)`. For each 10-K, all distinct non-dimensional USD values reported for the
two periods in that filing (excluding amounts below $10) are tested with the chi-square statistic (8 d.f.) and the mean absolute
deviation (MAD). MAD bands follow Nigrini: <0.006 close, <0.012 acceptable, <0.015 marginal, otherwise nonconformity.

Reliability: chi-square needs expected counts of at least 5 in every cell, i.e. n >= 110 (the smallest expected share, digit 9, is
4.6%). Below that the result is marked unreliable. For very large n chi-square rejects trivial deviations, so MAD is preferred.
Filings contain XBRL values that are arithmetic totals of other values, rounded, or constrained by accounting identities;
Benford conformity is not expected to hold perfectly for them and the test is a weak signal at the filing level.

## 6. Composite score

Logistic regression with `class_weight="balanced"`, L2 penalty at the default `C = 1`, median imputation and standardisation
fitted **inside each training fold**. The feature sets are pre-specified:

* core: DSRI, GMI, AQI, SGI, TATA, receivables-growth-minus-revenue-growth;
* extended: core + Benford MAD + (NI - CFO)/revenue.

No hyper-parameter or feature selection uses any test fold.

## 7. Validation design

* **Unit of analysis:** firm-year (a 10-K). **Positive:** a case company's 10-K for a fiscal year that its Item 4.02 8-K
  (or the enforcement order) says was misstated, filed before the cut-off. **Negative:** a matched control's 10-K for the same
  fiscal year. Every other firm-year is scored for display but never used to fit or evaluate.
* **Leave-one-company-out** cross-validation: all rows of a company are held out together, so the model never sees the
  company it scores. This also prevents a company's controls/cases from appearing on both sides of a split.
* **Operating point:** a row is flagged if its score exceeds the 90th percentile of *training-fold control* scores
  (target false-positive rate of 10%, chosen without the held-out company). The Beneish baseline is also reported at its fixed -1.78.
* **Confidence intervals:** percentile bootstrap that resamples whole companies (cases and controls separately, so every replicate has
  both classes), 95%.
* **Permutation test:** AUC when case/control labels are shuffled across companies.
* **Prevalence adjustment:** misstated firm-years make up a large share of the evaluation sample (see results.json); the real-world rate is far lower. Precision at
  assumed prevalences of 1% and 5% is derived from the sample TPR/FPR. These are illustrations of the base-rate problem, not measurements.

## 8. Look-ahead discipline

For every case, only 10-Ks **filed strictly before** the cut-off survive into the panel. The cut-off is the earlier of
(a) the Item 4.02 8-K filing date and (b) the first earlier public signal I could verify in an EDGAR filing (NT 10-K/10-Q, 8-K).
`validation.assert_no_lookahead` re-checks this on every run and is covered by tests.
**Lead time** = cut-off date minus the filing date of the earliest flagged misstated-year 10-K, in years and quarters.

## 9. Not done / not possible

* Quarterly filings are not scored (10-Q XBRL is available but the labelled misstated periods are annual).
* Controls are screened for Item 4.02 filings only; undisclosed ("stealth") restatements, SEC investigations without a 4.02, and
  enforcement actions without a restatement cannot be ruled out.
* The case set is chosen with hindsight from well-known failures that also happened to have XBRL data; results will flatter
  any detector.
