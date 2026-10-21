"""Benford's-law first-digit test.

Benford (1938) observed that in many naturally occurring sets of numbers the leading digit
``d`` appears with probability ``log10(1 + 1/d)``. Nigrini popularised its use on accounting
data. Departures can indicate fabricated or heavily rounded figures, but they also arise
innocently, so the test is a screening signal only.

Reliability limits implemented here:

* Chi-square needs expected counts of at least 5 in every cell. The smallest expected share is
  ``log10(10/9) = 4.6%`` (digit 9), so ``n >= 110`` is the minimum; below that
  :func:`benford_test` marks the result ``reliable=False``.
* Chi-square is over-powered for large ``n`` (tiny, economically meaningless deviations become
  "significant"), so MAD - which does not grow with ``n`` - is the preferred statistic.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import stats

DIGITS = np.arange(1, 10)
EXPECTED = np.log10(1 + 1 / DIGITS)

#: Minimum sample for the chi-square approximation (expected count >= 5 for digit 9).
MIN_N_RELIABLE = int(np.ceil(5 / EXPECTED.min()))
#: Above this n, chi-square flags trivial deviations; lean on MAD instead.
HIGH_POWER_N = 5000

#: Nigrini's MAD conformity bands for first-digit tests (upper bounds).
MAD_BANDS = (
    (0.006, "close conformity"),
    (0.012, "acceptable conformity"),
    (0.015, "marginally acceptable"),
    (np.inf, "nonconformity"),
)


@dataclass(frozen=True)
class BenfordResult:
    n: int
    chi2: float
    p_value: float
    mad: float
    conformity: str
    reliable: bool


def first_digits(values) -> np.ndarray:
    """Leading non-zero digit of each |value|; zeros and non-finite values are dropped."""
    v = np.abs(np.asarray(values, dtype=float))
    v = v[np.isfinite(v) & (v > 0)]
    exponent = np.floor(np.log10(v))
    lead = np.floor(v / 10.0**exponent).astype(int)
    # Guard against floating-point edge cases such as 1000 -> 9.999999 * 10**2
    lead = np.where(lead >= 10, 1, lead)
    return lead


def digit_counts(values) -> np.ndarray:
    d = first_digits(values)
    return np.bincount(d, minlength=10)[1:10]


def conformity_label(mad: float) -> str:
    for upper, label in MAD_BANDS:
        if mad < upper:
            return label
    return MAD_BANDS[-1][1]


def benford_test(counts) -> BenfordResult:
    """Chi-square and MAD of observed first-digit counts against Benford's law."""
    counts = np.asarray(counts, dtype=float)
    n = int(counts.sum())
    if n == 0:
        return BenfordResult(0, np.nan, np.nan, np.nan, "n/a", False)
    expected_counts = EXPECTED * n
    chi2 = float(((counts - expected_counts) ** 2 / expected_counts).sum())
    p = float(stats.chi2.sf(chi2, df=8))
    mad = float(np.abs(counts / n - EXPECTED).mean())
    return BenfordResult(n, chi2, p, mad, conformity_label(mad), n >= MIN_N_RELIABLE)
