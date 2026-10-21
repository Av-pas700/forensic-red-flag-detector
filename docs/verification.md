# Verification: computed ratios checked by hand against the source filings

Three ratios produced by the pipeline were recomputed independently from the figures printed in the companies' own 10-K
documents (fetched from `sec.gov/Archives`; the statement lines were located by text search and read). Amounts are in
thousands of USD as printed in the filing. `tests/test_verification.py` pins the same three values to the committed dataset so the
check cannot silently drift.

| # | Filing | Ratio | Inputs read from the filing | Hand result | Pipeline result |
|---|---|---|---|---|---|
| 1 | Synchronoss Technologies FY2016 10-K, accession 0001131554-17-000037 (filed 2017-02-27) | DSRI | Net revenues 476,750 (2016) and 428,117 (2015); accounts receivable, net 137,233 (2016) and 136,117 (2015), balance-sheet and income-statement lines | (137,233 / 476,750) / (136,117 / 428,117) = 0.28786 / 0.31793 = **0.9054** | **0.9054** |
| 2 | MiMedx Group FY2015 10-K, accession 0001376339-16-000138 (filed 2016-02-29) | SGI and GMI | Revenue 187,296 (2015) and 118,223 (2014); cost of sales 20,202 and 12,665; gross margin 167,094 and 105,558 | SGI = 187,296 / 118,223 = **1.5843**; gross margin 0.89214 (2015) and 0.89287 (2014), so GMI = 0.89287 / 0.89214 = **1.0008** | SGI **1.5843**, GMI **1.0008** |
| 3 | Kraft Heinz FY2017 10-K, accession 0001637459-18-000015 (filed 2018-02-16) | TATA | Net income/(loss) 10,990 (consolidated, cash-flow statement and income statement); "Net cash provided by operating activities was $527 million"; total assets 120,232 | (10,990 - 527) / 120,232 = **0.0870** | **0.0870** |

## What the checks found

* All three agree with the filings to the displayed precision. The pipeline's inputs equal the printed statements (units differ only by the
  factor of 1,000 between the filing and the XBRL values).
* **Bug found and fixed during verification.** The first version preferred the XBRL tag `NetIncomeLoss` (income attributable to the parent) over
  `ProfitLoss` (consolidated income). For Kraft Heinz FY2017 that is 10,999 versus the 10,990 shown in the cash-flow statement, which starts from
  consolidated income. Because TATA subtracts consolidated operating cash flow, the like-for-like input is consolidated income, so the tag order was
  changed (`statements.py`, decision 16 in `DECISIONS.md`) and the dataset and all results were regenerated. The change moved the headline numbers
  only marginally.
* Context that the ratios do not capture: Kraft Heinz's 2017 net income includes a one-off US tax-reform gain, which inflates TATA. The signal
  uses net income rather than income from continuing operations; this is listed as a limitation in the README.
