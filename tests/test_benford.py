import numpy as np
import pytest

from redflag.benford import (
    EXPECTED,
    MIN_N_RELIABLE,
    benford_test,
    digit_counts,
    first_digits,
)


def test_expected_distribution_sums_to_one():
    assert EXPECTED.sum() == pytest.approx(1.0)
    assert EXPECTED[0] == pytest.approx(0.30103, abs=1e-5)


def test_first_digits_handles_edge_cases():
    d = first_digits([0.0123, 9.99, 1000, -450, 0, np.nan, 1e12, 0.999999])
    assert d.tolist() == [1, 9, 1, 4, 1, 9]


def test_benford_distributed_sample_conforms():
    rng = np.random.default_rng(1)
    values = 10 ** rng.uniform(0, 7, 20_000)  # log-uniform data obeys Benford's law
    r = benford_test(digit_counts(values))
    assert r.n == 20_000
    assert r.mad < 0.006 and r.conformity == "close conformity"
    assert r.p_value > 0.01 and r.reliable


def test_uniform_digits_are_rejected():
    r = benford_test([500] * 9)  # every first digit equally likely - classic fabrication pattern
    assert r.p_value < 1e-6
    assert r.mad > 0.015 and r.conformity == "nonconformity"


def test_small_samples_are_marked_unreliable():
    rng = np.random.default_rng(2)
    r = benford_test(digit_counts(10 ** rng.uniform(0, 6, 60)))
    assert not r.reliable
    assert MIN_N_RELIABLE == 110  # ceil(5 / log10(10/9))


def test_empty_counts_do_not_crash():
    r = benford_test([0] * 9)
    assert r.n == 0 and np.isnan(r.mad) and not r.reliable
