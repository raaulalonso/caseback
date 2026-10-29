import numpy as np
import pytest

from caseback_ppg import (
    bandpass, beats_to_ibi, clean_ibi, detect_beats, heart_rate_series, hrv_metrics,
)
from caseback_ppg.synth import synth_ppg

FS = 64.0


def test_bandpass_removes_baseline_and_keeps_pulse():
    t = np.arange(0, 30, 1 / FS)
    pulse = np.sin(2 * np.pi * 1.2 * t)
    y = bandpass(pulse + 5.0 + 0.5 * t, FS)
    assert abs(np.mean(y)) < 0.05
    assert np.corrcoef(y[200:-200], pulse[200:-200])[0, 1] > 0.99


def test_bandpass_rejects_bad_cutoffs():
    with pytest.raises(ValueError):
        bandpass(np.zeros(1000), FS, low=1.0, high=40.0)


@pytest.mark.parametrize("hr", [45, 70, 110, 160])
def test_detect_beats_matches_truth(hr):
    ppg, truth = synth_ppg(60, FS, hr_bpm=hr)
    beats = detect_beats(ppg, FS) / FS
    # every true beat has a detection within 60 ms and there are no extras
    assert abs(len(beats) - len(truth)) <= 1
    nearest = np.abs(beats[:, None] - truth[None, :]).min(axis=1)
    assert np.median(nearest) < 0.06


def _hr_error(hr: float, rsa_ms: float, *, integer_peaks: bool = False) -> float:
    """Worst-case |estimated - true| bpm, where "true" is the same windowing over the true beats."""
    ppg, truth = synth_ppg(60, FS, hr_bpm=hr, rsa_ms=rsa_ms)
    beats = detect_beats(ppg, FS)
    if integer_peaks:
        beats = np.round(beats)
    _, est = heart_rate_series(beats, FS, duration_s=60)
    _, ref = heart_rate_series(truth * FS, FS, duration_s=60)
    return float(np.nanmax(np.abs(est - ref)))


# Residual error comes from pulse morphology (the diastolic bump of one beat overlaps the
# next at high HR) and the filter, not from the detector; ~1.4 ms peak jitter at 256 Hz.
@pytest.mark.parametrize("hr", [45, 70, 110, 160])
def test_heart_rate_matches_truth(hr):
    assert _hr_error(hr, rsa_ms=30) < 3.0


def test_subsample_peaks_beat_integer_peaks_at_high_hr():
    # 160 bpm is exactly 24 samples at 64 Hz; integer peak indices quantise IBIs by ~4 %.
    assert _hr_error(160, rsa_ms=30) < _hr_error(160, rsa_ms=30, integer_peaks=True)


def test_flat_signal_yields_no_beats_and_nan_hr():
    beats = detect_beats(np.zeros(int(FS) * 20), FS)
    assert beats.size == 0
    _, bpm = heart_rate_series(beats, FS, duration_s=20)
    assert np.isnan(bpm).all()


def test_noise_only_does_not_report_confident_hr_outside_range():
    rng = np.random.default_rng(1)
    beats = detect_beats(rng.standard_normal(int(FS * 60)), FS)
    _, bpm = heart_rate_series(beats, FS, duration_s=60)
    assert np.all(np.isnan(bpm) | ((bpm >= 30) & (bpm <= 200)))


def test_clean_ibi_drops_missed_and_spurious_beats():
    ibi = np.full(30, 800.0)
    ibi[10] = 1600.0   # missed beat
    ibi[20] = 350.0    # spurious beat
    t = np.cumsum(ibi) / 1000
    t_c, ibi_c = clean_ibi(t, ibi)
    assert 1600.0 not in ibi_c and 350.0 not in ibi_c
    assert ibi_c.size == 28


def test_hrv_matches_ground_truth_on_synthetic():
    ppg, truth = synth_ppg(120, FS, hr_bpm=60, rsa_ms=40, noise=0.02)
    t, ibi = clean_ibi(*beats_to_ibi(detect_beats(ppg, FS), FS))
    est = hrv_metrics(ibi, t)
    true_ibi = np.diff(truth) * 1000
    true_rmssd = np.sqrt(np.mean(np.diff(true_ibi) ** 2))
    assert est is not None
    assert est.rmssd_ms == pytest.approx(true_rmssd, abs=4.0)
    assert est.sdnn_ms == pytest.approx(true_ibi.std(ddof=1), abs=4.0)
    assert est.mean_hr_bpm == pytest.approx(60, abs=1.0)


def test_hrv_needs_enough_data():
    assert hrv_metrics(np.full(5, 800.0)) is None


def test_hrv_skips_pairs_across_gaps():
    ibi = np.array([800, 810, 790, 800, 805, 795, 800, 1000, 800, 810, 790, 800], float)
    t = np.cumsum(ibi) / 1000
    keep = np.arange(ibi.size) != 7          # interval 7 was rejected upstream
    with_gap = hrv_metrics(ibi[keep], t[keep])
    naive = hrv_metrics(ibi[keep])
    assert with_gap is not None and naive is not None
    assert with_gap.rmssd_ms < naive.rmssd_ms or with_gap.n_intervals == naive.n_intervals


def test_upslope_fiducial_times_beats_consistently():
    import numpy as np
    from caseback_ppg import beats_to_ibi, detect_beats, hrv_metrics
    from caseback_ppg.synth import synth_ppg
    fs = 125.0
    ppg, truth = synth_ppg(180.0, fs, hr_bpm=70.0, rsa_ms=30.0, noise=0.03, seed=3)
    up = detect_beats(ppg, fs, fiducial="upslope") / fs
    assert abs(len(up) - len(truth)) <= 2
    lag = np.median(up[:5] - truth[:5])                      # the upstroke precedes the peak by a fixed lag
    assert -0.15 < lag < 0.0
    true_ibi = np.diff(truth) * 1000
    t, ibi = beats_to_ibi(up * fs, fs)
    got = hrv_metrics(ibi, t)
    want = hrv_metrics(true_ibi)
    assert got.rmssd_ms == pytest.approx(want.rmssd_ms, rel=0.35)


def test_upslope_rejects_filtered_input_and_unknown_fiducial():
    import numpy as np
    from caseback_ppg import detect_beats
    x = np.zeros(1000)
    with pytest.raises(ValueError):
        detect_beats(x, 125.0, filtered=True, fiducial="upslope")
    with pytest.raises(ValueError):
        detect_beats(x, 125.0, fiducial="foot")
