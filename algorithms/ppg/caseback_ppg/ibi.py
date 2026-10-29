"""Inter-beat intervals."""

import numpy as np

MIN_IBI_MS = 300.0    # 200 bpm
MAX_IBI_MS = 2000.0   # 30 bpm
MAX_JUMP = 0.25       # relative deviation from the local median


def beats_to_ibi(beats: np.ndarray, fs: float) -> tuple[np.ndarray, np.ndarray]:
    """Return ``(t_s, ibi_ms)``: each interval stamped with the time of its closing beat."""
    beats = np.asarray(beats)
    if beats.size < 2:
        return np.empty(0), np.empty(0)
    return beats[1:] / fs, np.diff(beats) * 1000.0 / fs


def clean_ibi(t_s: np.ndarray, ibi_ms: np.ndarray, window: int = 5) -> tuple[np.ndarray, np.ndarray]:
    """Drop physiologically impossible intervals and outliers vs. the local median.

    Missed or spurious beats show up as intervals that are ~2x or ~0.5x their neighbours;
    HRV computed on them is meaningless, so they are removed rather than repaired.
    """
    t_s = np.asarray(t_s, dtype=float)
    ibi_ms = np.asarray(ibi_ms, dtype=float)
    keep = (ibi_ms >= MIN_IBI_MS) & (ibi_ms <= MAX_IBI_MS)
    t_s, ibi_ms = t_s[keep], ibi_ms[keep]
    if ibi_ms.size == 0:
        return t_s, ibi_ms
    half = window // 2
    ok = np.empty(ibi_ms.size, dtype=bool)
    for i in range(ibi_ms.size):
        local = np.median(ibi_ms[max(0, i - half): i + half + 1])
        ok[i] = abs(ibi_ms[i] - local) <= MAX_JUMP * local
    return t_s[ok], ibi_ms[ok]
