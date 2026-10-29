"""Heart rate from beats."""

import numpy as np

from .ibi import beats_to_ibi, clean_ibi


def heart_rate_series(
    beats: np.ndarray,
    fs: float,
    *,
    window_s: float = 8.0,
    step_s: float = 1.0,
    duration_s: float | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    """Return ``(t_s, bpm)`` sampled every ``step_s`` from the median IBI in a trailing window.

    Windows with no valid interval yield NaN so callers can tell "no reading" from a value.
    """
    t_ibi, ibi = clean_ibi(*beats_to_ibi(beats, fs))
    if duration_s is None:
        duration_s = (beats[-1] / fs) if len(beats) else 0.0
    t_out = np.arange(window_s, duration_s + 1e-9, step_s)
    bpm = np.full(t_out.size, np.nan)
    for k, t in enumerate(t_out):
        sel = ibi[(t_ibi > t - window_s) & (t_ibi <= t)]
        if sel.size:
            bpm[k] = 60000.0 / np.median(sel)
    return t_out, bpm
