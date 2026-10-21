# Forensic Red-Flag Detector

> **Disclaimer.** This is a research and portfolio project. It is **not investment advice**. A "flag" means a filing
> resembles filings of companies that later restated; it indicates *elevated risk worth investigating*, **not proof of
> fraud, intent or wrongdoing**. Many flagged companies are honest, and most manipulators are not flagged.

## Summary

The tool screens US company financials from SEC EDGAR (XBRL) for accounting-manipulation signals - the Beneish M-score,
accruals quality, receivables-versus-revenue and earnings-versus-cash-flow divergence, and a Benford first-digit test -
and asks a practical question: *using only filings available before the problem became public, would these signals have
flagged real companies that later restated or faced SEC accounting action?* It is validated on **{{n_cases}} verified US
cases** against **{{n_controls}} matched healthy peers** ({{n_pos}} misstated and {{n_neg}} control firm-years, fiscal
{{fy_min}}-{{fy_max}}) with leave-one-company-out cross-validation and company-level bootstrap confidence intervals.
**The honest headline is modest:** the published Beneish M-score has a ROC-AUC of {{auc_beneish_fixed_full}}, flags {{det_beneish_fixed}}
cases ahead of their restatement (median lead {{lead_med_y_beneish_fixed}} years) at a {{fpr_beneish_fixed}} false-positive rate, and
my refitted composite score did **not** improve on it. With this few positives the study is a *case-study validation, not
proof of predictive power*.

## Key results

All numbers below are written by `scripts/render_docs.py` from `reports/results.json`; `scripts/check_claims.py` fails the build if
this README disagrees with the code output. Out-of-sample = leave-one-company-out; CIs = {{n_boot}}-replicate bootstrap over companies.

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
| `docs/` | `methods.md`, `case_selection.md` (sources and dates), `verification.md` (hand checks) |
| `reports/` | `memo.md` / `memo.pdf` (2 pages), `results.json`, figures, tables |
| `app/dashboard.py` | Streamlit dashboard |
| `DECISIONS.md` | every judgement call with a one-line reason |

## Data sources

* SEC EDGAR XBRL `companyfacts`, `submissions` and `frames` APIs (public; <https://www.sec.gov/edgar/sec-api-documentation>).
* SEC Form 8-K **Item 4.02** (non-reliance on previously issued financials) filings as the primary source for each case.
* SEC enforcement releases, litigation releases and press releases (URLs and dates in `docs/case_selection.md`); Item 1.03 8-Ks for bankruptcy.
* XBRL coverage starts around 2009 (large filers) to 2011 (smaller filers), so **Enron, WorldCom and other pre-XBRL cases are out of scope**.

## Limitations

* **Small sample, hindsight selection.** {{n_cases}} cases picked from well-known failures that also had XBRL coverage; results flatter any detector.
  The confidence intervals are wide and there are only a handful of independent companies.
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

1. Widen the sample (more years, more restatement types, SPAC-era restatements) and add quarterly 10-Q signals, where labelled periods are shorter.
2. Pre-register the model and threshold, then score **prospectively** each filing season and report realised hit rates against a realistic base rate.
3. Use income from continuing operations and industry-adjusted indices (z-scores within SIC groups) to cut false positives from M&A and cyclicality.
4. Add text signals (MD&A language, auditor changes, late-filing notices) that often precede restatements and are independent of the numbers.
5. Calibrate the composite probabilistically and report cost-weighted decision curves for an audit-committee audience.

## Licence

MIT - see `LICENSE`.
