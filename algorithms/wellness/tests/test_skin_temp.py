import numpy as np
import pytest

from caseback_wellness.skin_temp import (TempBaseline, divider_resistance, fit_two_point, night_value,
                                      ntc_to_celsius, on_wrist)


def test_ntc_known_points():
    assert ntc_to_celsius(10_000.0) == pytest.approx(25.0, abs=1e-6)
    assert ntc_to_celsius(6_404.0) == pytest.approx(37.0, abs=0.05)
    assert divider_resistance(0.5) == pytest.approx(10_000.0)
    assert ntc_to_celsius(divider_resistance(0.5)) == pytest.approx(25.0, abs=1e-3)


def test_two_point_calibration():
    gain, off = fit_two_point((1.2, 36.4), (0.0, 37.0))
    assert gain * 1.2 + off == pytest.approx(0.0) and gain * 36.4 + off == pytest.approx(37.0)
    with pytest.raises(ValueError):
        fit_two_point((30.0, 30.4), (30.0, 30.5))


def test_on_wrist_rejects_room_temperature_and_jumps():
    fs = 1 / 30
    t = np.r_[np.full(40, 22.0), np.linspace(22, 33, 20), np.full(100, 33.0)]
    m = on_wrist(t, fs)
    assert not m[:40].any() and m[-50:].all()


def test_night_value_needs_enough_asleep_time_and_baseline_gates():
    fs = 1 / 30
    n = int(8 * 3600 * fs)
    temp = np.full(n, 33.2)
    asleep = np.ones(n, bool)
    assert night_value(temp, asleep, fs) == pytest.approx(33.2)
    assert np.isnan(night_value(temp, np.zeros(n, bool), fs))
    b = TempBaseline()
    assert np.isnan(b.deviation(33.5))                     # calibrating
    for v in (33.2, 33.1, 33.3, 33.2, 33.2):
        b.add(v)
    assert b.deviation(33.7) == pytest.approx(0.5)
    b.add(float("nan"))
    assert len(b.nights) == 5
