import importlib.util
from pathlib import Path

import numpy as np
import pytest

_spec = importlib.util.spec_from_file_location("bootstrap", Path(__file__).parents[1] / "tools" / "bootstrap.py")
bootstrap = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bootstrap)


def test_interval_brackets_the_mean_and_is_reproducible():
    x = np.array([1.0, 2.0, 3.0, 4.0, 10.0])
    m, lo, hi = bootstrap.bootstrap_ci(x)
    assert m == pytest.approx(4.0) and lo < m < hi
    assert lo >= x.min() and hi <= x.max()
    assert bootstrap.bootstrap_ci(x) == (m, lo, hi)


def test_constant_values_give_a_degenerate_interval():
    assert bootstrap.bootstrap_ci(np.full(6, 2.5)) == (2.5, 2.5, 2.5)


def test_coverage_of_the_true_mean_is_near_nominal():
    rng = np.random.default_rng(1)
    hits = 0
    for k in range(200):
        _, lo, hi = bootstrap.bootstrap_ci(rng.normal(5.0, 2.0, size=30), n_boot=400, seed=k)
        hits += lo <= 5.0 <= hi
    assert 0.88 <= hits / 200 <= 0.99


def test_weighted_mean_matches_the_pooled_value():
    vals, w = np.array([1.0, 3.0, 5.0]), np.array([100.0, 100.0, 200.0])
    m, lo, hi = bootstrap.weighted_mean_ci(vals, w)
    assert m == pytest.approx(3.5) and lo <= m <= hi


def test_arbitrary_statistic_and_min_size():
    xy = np.column_stack([np.arange(20.0), 2 * np.arange(20.0) + 1])
    r, lo, hi = bootstrap.bootstrap_ci(xy, lambda a: np.corrcoef(a[:, 0], a[:, 1])[0, 1])
    assert r == pytest.approx(1.0) and hi == pytest.approx(1.0)
    with pytest.raises(ValueError):
        bootstrap.bootstrap_ci([1.0])


def test_t_interval_contains_the_mean():
    m, lo, hi = bootstrap.t_interval([4.0, 5.0, 6.0, 5.5, 4.5])
    assert lo < m < hi and m == pytest.approx(5.0)
