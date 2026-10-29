import math

import pytest

from caseback_wellness.readiness import Baseline, DayInputs, readiness

NORMAL = DayInputs(rhr_bpm=55, rmssd_ms=60, sleep_hours=8.0, sleep_efficiency=0.9, temp_dev_c=0.0)


def _base(days=20):
    b = Baseline()
    for i in range(days):
        b.update(DayInputs(rhr_bpm=55 + (i % 3) - 1, rmssd_ms=60 * math.exp(0.05 * ((i % 4) - 1.5))))
    return b


def test_calibrating_until_min_days_then_scored():
    r = readiness(NORMAL, _base(3))
    assert r.score is None and r.band == "calibrating"
    assert readiness(NORMAL, _base(20)).score is not None


def test_normal_day_is_near_the_middle_and_better_inputs_never_lower_it():
    b = _base()
    mid = readiness(NORMAL, b).score
    assert 40 <= mid <= 75
    better = [DayInputs(53, 60, 8, .9, 0), DayInputs(55, 75, 8, .9, 0), DayInputs(55, 60, 8.5, .9, 0),
              DayInputs(55, 60, 8, .95, 0)]
    for d in better:
        assert readiness(d, b).score >= mid
    worse = [DayInputs(62, 60, 8, .9, 0), DayInputs(55, 35, 8, .9, 0), DayInputs(55, 60, 5, .9, 0),
             DayInputs(55, 60, 8, .9, 1.0)]
    for d in worse:
        assert readiness(d, b).score < mid


def test_missing_inputs_lower_confidence_not_invent_values():
    b = _base()
    full = readiness(NORMAL, b)
    partial = readiness(DayInputs(rhr_bpm=55, rmssd_ms=60), b)
    assert full.confidence == pytest.approx(1.0) and partial.confidence == pytest.approx(0.65)
    assert set(partial.components) == {"rhr", "hrv"}
    assert readiness(DayInputs(), b).band == "no data"


def test_baseline_ignores_a_single_extreme_day_and_bands():
    b = _base()
    before = b.mean["rhr"]
    b.update(DayInputs(rhr_bpm=120))
    assert b.mean["rhr"] - before < 2.0
    assert readiness(DayInputs(rhr_bpm=75, rmssd_ms=20, sleep_hours=4, temp_dev_c=1.2), b).band == "low"
    assert readiness(DayInputs(rhr_bpm=50, rmssd_ms=95, sleep_hours=9, sleep_efficiency=.95), b).band == "high"
