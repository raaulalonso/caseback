"""Signal conditioning."""

import numpy as np
from scipy.signal import sosfiltfilt, butter


def bandpass(x: np.ndarray, fs: float, low: float = 0.5, high: float = 8.0, order: int = 3) -> np.ndarray:
    """Zero-phase Butterworth band-pass. Removes baseline wander and high-frequency noise.

    0.5-8 Hz keeps the pulse fundamental (30-240 bpm) and its first harmonics.
    """
    if not 0 < low < high < fs / 2:
        raise ValueError(f"need 0 < low < high < fs/2, got low={low} high={high} fs={fs}")
    x = np.asarray(x, dtype=float)
    sos = butter(order, [low, high], btype="bandpass", fs=fs, output="sos")
    # sosfiltfilt needs more samples than its padding; short input is a caller bug.
    if x.size < 3 * (2 * sos.shape[0] + 1) * 3:
        raise ValueError("signal too short to filter")
    return sosfiltfilt(sos, x)
