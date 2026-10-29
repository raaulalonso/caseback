"""Skin temperature: NTC conversion, on-wrist detection and nightly deviation from a personal baseline.

Absolute wrist skin temperature depends on the room, the strap and the sensor, so the useful quantity is the
*deviation* of tonight's median from your own recent nights. Only the conversion and the deviation logic are
tested here (synthetic data): no public dataset carries this sensor, and the NTC accuracy on the real device is
unmeasured. Calibrate the sensor against a reference thermometer (two points, e.g. ice water and a 37 C bath)
with :func:`fit_two_point` before trusting absolute values.
"""

from dataclasses import dataclass, field

import numpy as np

T25_K = 298.15


def ntc_to_celsius(resistance_ohm: np.ndarray | float, r25_ohm: float = 10_000.0, beta: float = 3435.0):
    """Beta-equation NTC thermistor conversion: 1/T = 1/T25 + ln(R/R25)/beta."""
    r = np.asarray(resistance_ohm, dtype=float)
    inv_t = 1.0 / T25_K + np.log(r / r25_ohm) / beta
    return 1.0 / inv_t - 273.15


def divider_resistance(adc_fraction: np.ndarray | float, r_series_ohm: float = 10_000.0):
    """NTC resistance from a divider with the NTC on the low side: fraction = R_ntc / (R_ntc + R_series)."""
    f = np.clip(np.asarray(adc_fraction, dtype=float), 1e-6, 1 - 1e-6)
    return r_series_ohm * f / (1.0 - f)


def fit_two_point(measured_c: tuple[float, float], reference_c: tuple[float, float]) -> tuple[float, float]:
    """Gain and offset so that ``reference = gain * measured + offset`` from two calibration points."""
    (m0, m1), (r0, r1) = measured_c, reference_c
    if abs(m1 - m0) < 1.0:
        raise ValueError("calibration points must differ by at least 1 C")
    gain = (r1 - r0) / (m1 - m0)
    return gain, r0 - gain * m0


def on_wrist(temp_c: np.ndarray, fs_hz: float, *, lo: float = 28.0, hi: float = 39.5,
             max_rate_c_per_min: float = 1.0) -> np.ndarray:
    """Boolean mask of samples plausibly touching skin: in range and not changing faster than a real skin does."""
    t = np.asarray(temp_c, dtype=float)
    ok = (t >= lo) & (t <= hi) & ~np.isnan(t)
    n = max(1, int(round(fs_hz * 60)))
    if len(t) > n:
        rate = np.abs(np.r_[np.zeros(n), t[n:] - t[:-n]])
        ok &= rate <= max_rate_c_per_min * 1.0
    return ok


def night_value(temp_c: np.ndarray, asleep: np.ndarray, fs_hz: float, *, min_minutes: float = 120.0) -> float:
    """Median skin temperature over asleep, on-wrist samples; NaN if there are fewer than ``min_minutes``."""
    t = np.asarray(temp_c, dtype=float)
    m = on_wrist(t, fs_hz) & np.asarray(asleep, dtype=bool)
    if m.sum() / fs_hz / 60.0 < min_minutes:
        return float("nan")
    return float(np.median(t[m]))


@dataclass
class TempBaseline:
    """Median of the last ``window`` nights; a deviation is only reported after ``min_nights`` nights."""
    window: int = 14
    min_nights: int = 5
    nights: list[float] = field(default_factory=list)

    def deviation(self, value: float) -> float:
        """Tonight minus the baseline, or NaN while calibrating or when tonight is missing."""
        if np.isnan(value) or len(self.nights) < self.min_nights:
            return float("nan")
        return float(value - np.median(self.nights[-self.window:]))

    def add(self, value: float) -> None:
        if not np.isnan(value):
            self.nights.append(float(value))
