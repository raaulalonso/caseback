"""Readiness score, 0-100, relative to your own recent baseline.

This is a design, not a measurement. There is no ground truth for "readiness", so it cannot be validated
against anything; what is tested is that it behaves sensibly (better inputs never lower it, a normal day
sits at 50, missing inputs lower the confidence rather than being guessed, a short history is reported as
calibrating). The weights and scales below are choices, listed here so they can be argued with. It is not a
medical or clinical indicator.

Components, each as a z-score against the personal baseline, positive = better than usual:
    resting HR     (baseline - today) / sd, sd >= 2 bpm
    HRV            (ln RMSSD - baseline) / sd, sd >= 0.10
    sleep          0.65 * duration/need + 0.35 * efficiency-scaled, mapped so 8 h at 90 % efficiency is ~ +0.4
    skin temp      -(|deviation| - 0.2 C)+ / 0.3 C   (only large deviations count)
score = 100 * Phi(weighted mean z over the available components). Bands: >= 67 high, 33-67 moderate, < 33 low.
"""

from dataclasses import dataclass, field
from math import erf, log, sqrt

WEIGHTS = {"hrv": 0.35, "rhr": 0.30, "sleep": 0.25, "temp": 0.10}
MIN_DAYS = 7
EWMA_DAYS = 21
SD_FLOOR = {"rhr": 2.0, "hrv": 0.10}


@dataclass(frozen=True)
class DayInputs:
    rhr_bpm: float | None = None            # lowest sustained resting HR of the night
    rmssd_ms: float | None = None           # nocturnal RMSSD
    sleep_hours: float | None = None
    sleep_efficiency: float | None = None   # asleep / in bed, 0..1
    temp_dev_c: float | None = None         # nightly skin-temperature deviation from baseline


@dataclass
class Baseline:
    """Exponentially weighted mean and variance per metric, updated with winsorised values."""
    alpha: float = 2.0 / (EWMA_DAYS + 1)
    days: int = 0
    mean: dict[str, float] = field(default_factory=dict)
    var: dict[str, float] = field(default_factory=dict)

    def update(self, day: DayInputs) -> None:
        for key, x in (("rhr", day.rhr_bpm), ("hrv", None if day.rmssd_ms in (None, 0) else log(day.rmssd_ms))):
            if x is None:
                continue
            if key not in self.mean:
                self.mean[key], self.var[key] = x, SD_FLOOR[key] ** 2
                continue
            sd = max(sqrt(self.var[key]), SD_FLOOR[key])
            x = min(max(x, self.mean[key] - 3 * sd), self.mean[key] + 3 * sd)
            d = x - self.mean[key]
            self.mean[key] += self.alpha * d
            self.var[key] = (1 - self.alpha) * (self.var[key] + self.alpha * d * d)
        self.days += 1


@dataclass(frozen=True)
class Readiness:
    score: float | None
    band: str                # "high" | "moderate" | "low" | "calibrating" | "no data"
    confidence: float        # share of the total weight that was available, 0..1
    components: dict[str, float]


def _phi(z: float) -> float:
    return 0.5 * (1.0 + erf(z / sqrt(2.0)))


def sleep_z(hours: float, efficiency: float | None, need_h: float = 8.0) -> float:
    dur = min(max(hours / need_h, 0.0), 1.1)
    eff = 0.9 if efficiency is None else min(max((efficiency - 0.75) / 0.2, 0.0), 1.0)
    score01 = 0.65 * dur + 0.35 * eff
    return (score01 - 0.75) / 0.2 if efficiency is not None else (dur - 0.75) / 0.2


def readiness(day: DayInputs, base: Baseline, *, need_h: float = 8.0) -> Readiness:
    z: dict[str, float] = {}
    if day.rhr_bpm is not None and "rhr" in base.mean:
        z["rhr"] = (base.mean["rhr"] - day.rhr_bpm) / max(sqrt(base.var["rhr"]), SD_FLOOR["rhr"])
    if day.rmssd_ms and "hrv" in base.mean:
        z["hrv"] = (log(day.rmssd_ms) - base.mean["hrv"]) / max(sqrt(base.var["hrv"]), SD_FLOOR["hrv"])
    if day.sleep_hours is not None:
        z["sleep"] = sleep_z(day.sleep_hours, day.sleep_efficiency, need_h)
    if day.temp_dev_c is not None:
        z["temp"] = -max(abs(day.temp_dev_c) - 0.2, 0.0) / 0.3
    if not z:
        return Readiness(None, "no data", 0.0, {})
    conf = sum(WEIGHTS[k] for k in z)
    if base.days < MIN_DAYS:
        return Readiness(None, "calibrating", conf, z)
    total = sum(WEIGHTS[k] * v for k, v in z.items()) / conf
    score = 100.0 * _phi(total)
    band = "high" if score >= 67 else "low" if score < 33 else "moderate"
    return Readiness(round(score, 1), band, conf, z)
