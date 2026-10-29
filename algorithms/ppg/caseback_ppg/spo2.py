"""Blood-oxygen saturation (SpO2) from red and infrared PPG: ratio of ratios plus a calibration curve.

    R = (AC_red / DC_red) / (AC_ir / DC_ir)        SpO2 ~= a - b * R

This module is implemented and tested on synthetic signals only. No public dataset carries raw red/IR PPG
with a reference oximeter, so the default curve (a=110, b=25, the textbook approximation) is NOT a
calibration of any Caseback sensor. It must be fitted with :func:`fit_calibration` on paired recordings from the
real hardware against a reference pulse oximeter over a controlled desaturation range (the fit refuses a narrow
reference range) before the number is shown to anyone as a measurement.

Quality gating returns NaN instead of a value when the window cannot be trusted: too little pulsatile signal
(perfusion index), red and IR AC components that do not move together (noise or motion), or too much
accelerometer activity.
"""

from dataclasses import dataclass

import numpy as np

from .filters import bandpass

DEFAULT_A, DEFAULT_B = 110.0, 25.0


@dataclass(frozen=True)
class Spo2Window:
    r: float               # ratio of ratios, NaN when the window is rejected
    spo2: float            # percent, NaN when rejected
    perfusion_index: float  # AC/DC of the IR channel, in percent
    coherence: float       # correlation between red and IR AC components, 0..1
    reason: str            # "ok" or why the window was rejected


def ratio_of_ratios(red: np.ndarray, ir: np.ndarray, fs: float) -> tuple[float, float, float]:
    """Return (R, IR perfusion index in %, red/IR AC correlation) for one window.

    AC is the band-passed 0.5-4 Hz signal, DC the mean of the raw signal. Instead of a ratio of RMS values
    (biased by noise power), R comes from the slope of red AC against IR AC: total least squares, so noise
    in either channel does not bias it.
    """
    red, ir = np.asarray(red, float), np.asarray(ir, float)
    dc_red, dc_ir = red.mean(), ir.mean()
    if dc_red <= 0 or dc_ir <= 0:
        return float("nan"), 0.0, 0.0
    ar, ai = bandpass(red, fs, 0.5, 4.0), bandpass(ir, fs, 0.5, 4.0)
    ar, ai = ar / dc_red, ai / dc_ir
    cov = np.cov(np.vstack([ai, ar]))
    # principal axis of (ir, red): slope of the dominant direction
    w, v = np.linalg.eigh(cov)
    major = v[:, np.argmax(w)]
    if abs(major[0]) < 1e-12:
        return float("nan"), 0.0, 0.0
    r = major[1] / major[0]
    corr = float(np.corrcoef(ai, ar)[0, 1]) if ai.std() > 0 and ar.std() > 0 else 0.0
    pi = float(np.sqrt(2) * ai.std() * 100.0)
    return float(abs(r)), pi, abs(corr)


def spo2_from_r(r: float, a: float = DEFAULT_A, b: float = DEFAULT_B) -> float:
    return float(np.clip(a - b * r, 0.0, 100.0))


MIN_PAIRS, MIN_R_SPAN, MIN_SPO2_SPREAD = 10, 0.05, 5.0


def fit_calibration(r: np.ndarray, spo2_ref: np.ndarray) -> tuple[float, float]:
    """Least-squares (a, b) of spo2 = a - b*R from paired windows and a reference oximeter.

    Refuses fits that cannot constrain the slope: fewer than 10 pairs, R spanning less than 0.05, or reference SpO2
    spanning less than 5 points. Healthy adults at rest sit at 96-99 %, so a resting-only session is refused: the
    calibration needs a controlled desaturation range (the reference has to reach well below 95 %).
    """
    r, y = np.asarray(r, float), np.asarray(spo2_ref, float)
    ok = ~(np.isnan(r) | np.isnan(y))
    if ok.sum() < MIN_PAIRS:
        raise ValueError(f"need at least {MIN_PAIRS} paired windows, got {int(ok.sum())}")
    if np.ptp(r[ok]) < MIN_R_SPAN:
        raise ValueError(f"R spans only {np.ptp(r[ok]):.3f}; need at least {MIN_R_SPAN}")
    if np.ptp(y[ok]) < MIN_SPO2_SPREAD:
        raise ValueError(f"reference SpO2 spans only {np.ptp(y[ok]):.1f} points (need at least {MIN_SPO2_SPREAD:g}): "
                         "a resting-only recording cannot constrain the slope; include a controlled desaturation range")
    slope, intercept = np.polyfit(r[ok], y[ok], 1)
    return float(intercept), float(-slope)


def spo2_window(red: np.ndarray, ir: np.ndarray, fs: float, *, acc_std: float | None = None,
                a: float = DEFAULT_A, b: float = DEFAULT_B, min_pi: float = 0.2, min_coherence: float = 0.9,
                max_acc_std: float = 0.15) -> Spo2Window:
    """SpO2 for one window (8-30 s is typical). ``acc_std`` is the accelerometer magnitude std in g."""
    r, pi, coh = ratio_of_ratios(red, ir, fs)
    reason = "ok"
    if np.isnan(r):
        reason = "no signal"
    elif acc_std is not None and acc_std > max_acc_std:
        reason = "motion"
    elif pi < min_pi:
        reason = "low perfusion"
    elif coh < min_coherence:
        reason = "channels disagree"
    if reason != "ok":
        return Spo2Window(float("nan"), float("nan"), pi, coh, reason)
    return Spo2Window(r, spo2_from_r(r, a, b), pi, coh, reason)
