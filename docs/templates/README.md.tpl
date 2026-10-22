# Forensic Red-Flag Detector

> **Disclaimer.** This is a research and portfolio project. It is **not investment advice**. A "flag" means a filing
> resembles filings of companies that later restated; it indicates *elevated risk worth investigating*, **not proof of
> fraud, intent or wrongdoing**. Many flagged companies are honest, and most manipulators are not flagged.

## Summary

The tool screens US company financials from SEC EDGAR (XBRL) for accounting-manipulation signals - the Beneish M-score,
accruals quality, receivables-versus-revenue and earnings-versus-cash-flow divergence, and a Benford first-digit test -
and asks a practical question: *using only filings available before the problem became public, would these signals have
flagged real companies that later restated or faced SEC accounting action?* It is validated on **{{n_cases}} verified US
cases** with **{{n_controls}} matched healthy peers**, using leave-one-company-out cross-validation and company-level bootstrap
confidence intervals. To stop me fooling myself, the cases are split in two: **{{d_n_cases}} development cases** that I picked from memory and
studied while building the models, and **{{h_n_cases}} holdout cases** selected mechanically from SEC's Accounting and Auditing Enforcement
Release list under rules I committed to GitHub *before* scoring them (`docs/preregistration.md`), scored with rules frozen on the development set.
**Headline:** on the development cases the published Beneish M-score has a ROC-AUC of {{d_auc_beneish_fixed_full}};
on the untouched holdout it scores {{h_auc_beneish_fixed_full}}. {{h_reading}} My refitted composite never reliably beat the plain M-score.
With this few independent companies the study is a *case-study validation, not proof of predictive power*.

## Key results

All numbers below are written by `scripts/render_docs.py` from `reports/results.json`; `scripts/check_claims.py` fails the build if
this README disagrees with the code output. The table pools all {{n_cases}} cases (development + holdout) under leave-one-company-out validation, i.e. every company is scored by a model that never saw it; CIs = {{n_boot}}-replicate bootstrap over companies. The next section separates the cohorts.

{{table_models}}

* Evaluation sample: {{n_pos}} misstated vs {{n_neg}} control firm-years from {{n_cases}} case and {{n_controls}} control companies, so
  {{pr_prevalence}} of rows are positives. That is far above any real-world base rate, so **precision figures flatter live
  performance**: at an assumed 1% prevalence the baseline's implied precision is {{ppv_beneish_fixed_1}} (at 5%: {{ppv_beneish_fixed_5}}).
  These implied figures are arithmetic on the sample's recall and false-positive rate, not measurements.
* {{verdict_core}}
* {{verdict_extended}}
* {{verdict_anchored}} (This variant was added *after* seeing the pre-specified model underperform, so it is exploratory.)
* Permutation p-values for ROC-AUC (labels shuffled across companies): baseline {{perm_beneish_fixed}}, composite {{perm_core}}.
  {{perm_reading}} Dropping any single case moves the baseline AUC within {{jack_beneish_fixed}}.
* Where each test stands alone (raw signal, higher = riskier):

{{table_signals}}

* **Benford:** the first-digit test did **not** separate misstated from control filings (median MAD {{bf_med_cases}} vs {{bf_med_controls}};
  {{bf_nonconf_cases}} vs {{bf_nonconf_controls}} of filings "nonconforming"). Filings hold about {{bf_med_n}} reported values, mostly
  sums and rounded totals, so it is a weak filing-level test and I would not use it alone.

### Does it generalise? The untouched holdout

{{table_generalisation}}

* Holdout: {{h_n_pos}} misstated and {{h_n_neg}} control firm-years from {{h_n_cases}} cases and {{h_n_controls}} controls. {{h_core_reading}}
  Frozen composite minus baseline on the holdout: ROC-AUC difference {{h_diff_core}}. Permutation p-value for the baseline on the holdout: {{h_perm_beneish_fixed}}.
* The holdout cases are mechanical, so they include restatements the M-score has no reason to catch (for example a segment-reporting restatement that leaves consolidated numbers unchanged).
  That is the point: a prospective screen faces the same mixture.

![Development vs holdout](reports/figures/fig7_generalisation.png)

{{table_holdout_cases}}

### How often does the M-score flag an ordinary company?

Using the XBRL `frames` API, I scored **every US calendar-year filer with a classified balance sheet and complete inputs** ({{u_n_2015}} in 2015,
{{u_n_2019}} in 2019) and counted how many exceed the {{beneish_threshold}} cut-off: **{{u_flag_2015}} in 2015 and {{u_flag_2019}} in 2019**. That is higher than the false-positive rate
among my matched controls ({{fpr_beneish_fixed}}), so the realistic false-alarm rate is probably worse than the control sample suggests. Taking the universe flag rate as the
false-alarm rate, a 1% manipulation prevalence implies a precision of about {{ppv_univ_1_2015}} (2015) to {{ppv_univ_1_2019}} (2019). These universe values are as currently reported, not original, and
some flagged firms may truly have problems, so treat the figure as a sanity check on the base rate, not a measurement of precision.

### Sensitivity: income from continuing operations

Replacing net income by income from continuing operations in TATA (so one-off gains and discontinued operations stop distorting accruals) gives an M-score ROC-AUC of {{ops_auc_full}}; difference from the
baseline {{ops_diff_full}}. {{ops_reading}}

### Case-by-case lead times

Lead time = filing date of the earliest flagged misstated-year 10-K to the case cut-off (the earlier of the Item 4.02 date and any
earlier verified public signal).

{{table_cases}}

![Case timelines](reports/figures/fig2_case_timelines.png)
![ROC and PR](reports/figures/fig1_roc_pr.png)

## Architecture

```mermaid
flowchart LR
  A[SEC EDGAR APIs<br/>companyfacts, submissions, frames] --> B[edgar.py<br/>cached, 8 req/s]
  B --> C[statements.py<br/>point-in-time 10-K extraction]
  C --> D[cases.py + controls.py<br/>verified cases, matched peers]
  D --> E[(data/processed CSVs)]
  E --> F[features.py + benford.py<br/>Beneish, accruals, cash-flow, Benford]
  F --> G[scoring.py<br/>class-weighted logistic regression]
  G --> H[validation.py + analysis.py<br/>LOCO CV, bootstrap, lead times]
  H --> I[results.json, figures, tables]
  I --> J[report.py<br/>README, memo, CV bullets]
  I --> K[Streamlit dashboard]
  J --> L[check_claims.py<br/>numbers must match code output]
```

## How to run

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev,app,report]"

make reproduce      # offline: analysis -> figures -> README/memo -> claim check, from committed data/processed
make test           # pytest
make lint           # ruff
make dashboard      # Streamlit: watchlist, score breakdown, trends, case studies

# Rebuild the dataset from the SEC (needs an identifying User-Agent; cached and rate-limited to 8 req/s)
export SEC_USER_AGENT="Your Name your.email@example.com"   # or put it in a gitignored .env
make data
```

`make reproduce` needs no network and no credentials. `make data` re-verifies every Item 4.02 citation against EDGAR and fails
loudly if one is wrong.

## Repository layout

| Path | Purpose |
|---|---|
| `src/redflag/` | `edgar` ingestion, `statements` point-in-time extraction, `features`/`benford` signals, `scoring`, `validation`, `analysis`, `plotting`, `report` |
| `tests/` | {{n_tests}} pytest tests: Beneish hand-calculation, Benford on synthetic data, no-look-ahead guards, bootstrap/CV properties |
| `data/cases/` | hand-curated case table (`cases.csv`) and exclusions with reasons |
| `data/processed/` | committed extracts so the analysis reproduces offline |
| `docs/` | `methods.md`, `preregistration.md` (holdout rules fixed before scoring), `case_selection.md` (sources and dates), `verification.md` (hand checks) |
| `reports/` | `memo.md` / `memo.pdf` (2 pages), `results.json`, figures, tables |
| `app/dashboard.py` | Streamlit dashboard |
| `DECISIONS.md` | every judgement call with a one-line reason |

## Data sources

* SEC EDGAR XBRL `companyfacts`, `submissions` and `frames` APIs (public; <https://www.sec.gov/edgar/sec-api-documentation>).
* SEC Form 8-K **Item 4.02** (non-reliance on previously issued financials) filings as the primary source for each case.
* SEC enforcement releases, litigation releases and press releases (URLs and dates in `docs/case_selection.md`); Item 1.03 8-Ks for bankruptcy.
* XBRL coverage starts around 2009 (large filers) to 2011 (smaller filers), so **Enron, WorldCom and other pre-XBRL cases are out of scope**.

## Limitations

* **Few independent companies; two kinds of selection.** The {{d_n_cases}} development cases were picked from memory of famous failures (hindsight) and also used to build the models. The {{h_n_cases}} holdout
  cases are mechanical (SEC accounting-enforcement releases that also have an Item 4.02 and usable XBRL), so they are the fair test - but they still exclude firms without XBRL, without an enforcement release,
  or never caught. Confidence intervals are wide.
* **Controls are not certified clean.** They are US non-financial peers matched on industry, size and fiscal year with no Item 4.02 filing in
  their EDGAR history; undisclosed restatements or SEC action cannot be ruled out. Matching tiers: {{match_tiers}}.
* **Sample base rate is unrealistic**, so precision is inflated relative to live use.
* **Heterogeneous misstatements.** Revenue-recognition fraud, tax and inventory errors look different in the numbers; the M-score was fitted on earnings-overstatement cases.
* **Look-ahead discipline limits:** original 10-Ks only, cut-off at the earlier of the Item 4.02 date and a verified earlier signal; I could verify an earlier signal for only some cases.
* **Net income, not continuing-operations income**, enters TATA, so one-off gains (e.g. 2017 tax reform) distort it.
* Hertz (verified case) was dropped because its unclassified balance sheet makes two Beneish indices undefined; others dropped for missing pre-event XBRL (`docs/case_selection.md`).
* The pre-specified composite is refitted with about {{n_pos}} positives; no tuning was done, and none would be reliable at this size.

## Ethics note

Naming a company in a screen can harm it. Every case here has a public restatement or SEC action on the record and is cited to its
primary source; controls are named only as matched peers with no restatement on record and are not accused of anything. Outputs are framed as screening signals for further human review. The tool should not be used to
trade on, publicise or accuse; false positives are expected and are the *normal* cost of screening.

## What I would do next

1. **Test the one hypothesis the data suggest, properly:** the M-score may only work for revenue/receivable-type restatements (exploratory split above). Pre-register it and test it on a fresh sample of such cases, e.g. every
   revenue-related Item 4.02 filing, not only those that reached an SEC release.
2. Replace the matched-control false-positive rate with the universe flag rate everywhere, and calibrate a threshold for a stated base rate and cost ratio (decision curves for an audit-committee audience).
3. Add quarterly (10-Q) signals - needs year-to-date cash-flow handling and quarter-level labels, so it is a separate piece of work - and industry-adjusted indices to cut false positives from M&A and cyclicality.
4. Add text signals (MD&A language, auditor changes, late-filing notices) that often precede restatements and are independent of the numbers.
5. Score prospectively each filing season with the frozen rule and publish only aggregate hit rates (no named lists: precision this low would mostly accuse honest firms).

## Licence

MIT - see `LICENSE`.
