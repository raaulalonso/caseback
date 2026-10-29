"""Synthetic PPG with known ground truth, for tests and quick experiments."""

import numpy as np


def synth_ppg(
    duration_s: float,
    fs: float,
    *,
    hr_bpm: float = 70.0,
    rsa_ms: float = 30.0,
    noise: float = 0.05,
    wander: float = 0.5,
    seed: int = 0,
) -> tuple[np.ndarray, np.ndarray]:
    """Return ``(ppg, beat_times_s)``.

    Beat times follow a mean interval of ``60/hr_bpm`` modulated by a 0.25 Hz respiratory
    term (``rsa_ms`` amplitude) so HRV is non-zero and known. Each beat is a systolic
    gaussian plus a smaller, later diastolic one; baseline wander and white noise are added.
    """
    rng = np.random.default_rng(seed)
    mean_ibi = 60.0 / hr_bpm
    beats, t = [], 0.3
    while t < duration_s:
        beats.append(t)
        t += mean_ibi + (rsa_ms / 1000.0) * np.sin(2 * np.pi * 0.25 * t)
    beats = np.array(beats)

    ts = np.arange(int(duration_s * fs)) / fs
    x = np.zeros_like(ts)
    for b in beats:
        x += np.exp(-0.5 * ((ts - b) / 0.06) ** 2)
        x += 0.35 * np.exp(-0.5 * ((ts - b - 0.28) / 0.09) ** 2)
    x += wander * np.sin(2 * np.pi * 0.15 * ts + 1.0)
    x += noise * rng.standard_normal(ts.size)
    return x, beats
