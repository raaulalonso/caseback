import numpy as np
import pytest

from caseback_ppg import fit_calibration, spo2_from_r, spo2_window
from caseback_ppg.spo2 import ratio_of_ratios

FS = 50.0


def _pair(r_true, *, hr=72.0, seconds=20, pi=1.5, noise=0.0, seed=0, dc_red=90000.0, dc_ir=110000.0):
    """Red/IR PPG whose ratio of ratios is exactly ``r_true`` before noise."""
    rng = np.random.default_rng(seed)
    t = np.arange(int(seconds * FS)) / FS
    f = hr / 60
    pulse = np.sin(2 * np.pi * f * t) + 0.25 * np.sin(4 * np.pi * f * t + 0.6)
    ac_ir = pi / 100 / np.sqrt(2) * pulse / pulse.std()   # std*sqrt(2)*100 == pi (%)
    ir = dc_ir * (1 + ac_ir + noise * rng.normal(size=t.size))
    red = dc_red * (1 + r_true * ac_ir + noise * rng.normal(size=t.size))
    return red, ir


@pytest.mark.parametrize("r_true", [0.5, 0.6, 0.8, 1.0])
def test_ratio_of_ratios_recovers_true_r_without_noise(r_true):
    r, pi, coh = ratio_of_ratios(*_pair(r_true), FS)
    assert r == pytest.approx(r_true, rel=0.03)
    assert coh > 0.99 and pi > 0.5


def test_noise_does_not_bias_r():
    rs = [ratio_of_ratios(*_pair(0.7, noise=0.002, seed=s), FS)[0] for s in range(20)]
    assert np.mean(rs) == pytest.approx(0.7, abs=0.03)


def test_default_curve_and_window_result():
    res = spo2_window(*_pair(0.6), FS)
    assert res.reason == "ok"
    assert res.spo2 == pytest.approx(spo2_from_r(0.6), abs=1.0)
    assert 90 < res.spo2 < 100


def test_rejects_low_perfusion_motion_and_noise():
    assert spo2_window(*_pair(0.6, pi=0.02), FS).reason == "low perfusion"
    assert spo2_window(*_pair(0.6), FS, acc_std=0.5).reason == "motion"
    red, ir = _pair(0.6, noise=0.02)
    res = spo2_window(red, ir, FS)
    assert res.reason in {"channels disagree", "low perfusion"} and np.isnan(res.spo2)


def test_calibration_fit_recovers_curve():
    rng = np.random.default_rng(3)
    r = rng.uniform(0.45, 1.0, 200)
    ref = 104.0 - 17.0 * r + rng.normal(scale=0.3, size=r.size)
    a, b = fit_calibration(r, ref)
    assert (a, b) == pytest.approx((104.0, 17.0), abs=0.6)
    with pytest.raises(ValueError):
        fit_calibration(np.full(20, 0.6), np.full(20, 97.0))


def test_calibration_refuses_a_narrow_reference_range_or_few_pairs():
    rng = np.random.default_rng(4)
    r = rng.uniform(0.45, 1.0, 60)
    with pytest.raises(ValueError, match="resting-only"):
        fit_calibration(r, 97.5 + rng.uniform(-1.5, 1.5, r.size))         # 96-99 %: resting healthy adult
    with pytest.raises(ValueError, match="at least 10"):
        fit_calibration(r[:9], 104.0 - 17.0 * r[:9])
    with pytest.raises(ValueError, match="R spans"):
        fit_calibration(np.full(20, 0.6) + rng.uniform(0, 0.01, 20), np.linspace(88, 99, 20))
    a, b = fit_calibration(r, 104.0 - 17.0 * r)                              # 9.35 points of spread is accepted
    assert (a, b) == pytest.approx((104.0, 17.0), abs=1e-6)
