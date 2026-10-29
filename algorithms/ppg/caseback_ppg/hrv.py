"""Time-domain HRV."""

from dataclasses import dataclass

import numpy as np

MIN_INTERVALS = 10


@dataclass(frozen=True)
class HrvMetrics:
    mean_hr_bpm: float
    sdnn_ms: float
    rmssd_ms: float
    pnn50: float  # fraction 0..1
    n_intervals: int


def hrv_metrics(ibi_ms: np.ndarray, t_s: np.ndarray | None = None) -> HrvMetrics | None:
    """HRV from cleaned IBIs. Returns None when there is too little data.

    Successive differences (RMSSD, pNN50) are only valid between adjacent intervals. Pass
    ``t_s`` (closing-beat times from ``beats_to_ibi``) so pairs separated by a rejected
    interval are skipped; without it every pair is assumed adjacent.
    """
    ibi = np.asarray(ibi_ms, dtype=float)
    if ibi.size < MIN_INTERVALS:
        return None
    diff = np.diff(ibi)
    if t_s is not None:
        adjacent = np.diff(np.asarray(t_s, dtype=float)) * 1000.0 <= 1.5 * ibi[1:]
        diff = diff[adjacent]
    if diff.size == 0:
        return None
    return HrvMetrics(
        mean_hr_bpm=float(60000.0 / ibi.mean()),
        sdnn_ms=float(ibi.std(ddof=1)),
        rmssd_ms=float(np.sqrt(np.mean(diff**2))),
        pnn50=float(np.mean(np.abs(diff) > 50.0)),
        n_intervals=int(ibi.size),
    )
