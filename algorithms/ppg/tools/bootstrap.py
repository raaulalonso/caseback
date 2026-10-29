"""Bootstrap confidence intervals over recordings (or subjects), the unit that is actually independent.

Windows of 8 s that slide by 2 s share 6 s with their neighbours, so a window-level n (1328, 21 482) overstates
the precision. Resample the recordings instead: each replicate draws recordings with replacement and recomputes
the statistic. With a handful of recordings the percentile interval is itself rough; ``t_interval`` is given for
comparison and ``range`` of the inputs is always the honest worst case.

    from bootstrap import bootstrap_ci, weighted_mean_ci
    mean, lo, hi = bootstrap_ci(per_recording_mae)
    mean, lo, hi = weighted_mean_ci(per_recording_mae, windows_per_recording)   # reproduces a pooled (window-level) MAE
"""

from collections.abc import Callable

import numpy as np
from scipy import stats


def bootstrap_ci(x, stat: Callable[[np.ndarray], float] = np.mean, *, n_boot: int = 10000, level: float = 0.95,
                 seed: int = 0) -> tuple[float, float, float]:
    """``(statistic, lower, upper)``: percentile bootstrap over the first axis of ``x`` (recordings)."""
    x = np.asarray(x, dtype=float)
    n = len(x)
    if n < 2:
        raise ValueError("need at least 2 recordings to bootstrap")
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, n, size=(n_boot, n))
    reps = np.array([stat(x[i]) for i in idx])
    a = (1.0 - level) / 2.0
    lo, hi = np.quantile(reps, [a, 1.0 - a])
    return float(stat(x)), float(lo), float(hi)


def weighted_mean_ci(values, weights, **kw) -> tuple[float, float, float]:
    """Bootstrap over recordings of the weighted mean (e.g. per-recording MAE weighted by its number of windows,
    which equals the pooled window-level MAE)."""
    x = np.column_stack([np.asarray(values, float), np.asarray(weights, float)])
    return bootstrap_ci(x, lambda a: float(np.average(a[:, 0], weights=a[:, 1])), **kw)


def t_interval(x, level: float = 0.95) -> tuple[float, float, float]:
    """Student-t interval of the mean of ``x`` (one value per recording)."""
    x = np.asarray(x, dtype=float)
    m, se = x.mean(), stats.sem(x)
    lo, hi = stats.t.interval(level, len(x) - 1, loc=m, scale=se)
    return float(m), float(lo), float(hi)
