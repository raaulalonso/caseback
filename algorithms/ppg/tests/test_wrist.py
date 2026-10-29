import numpy as np
import pytest

from caseback_ppg import MotionCompensatedHR, track_wrist_hr

FS = 125.0


def _recording(seconds=60, hr_bpm=80.0, cadence_hz=1.7, artifact_gain=4.0, seed=0):
    """PPG = pulse + motion artifact that is a filtered copy of the accelerometer + noise."""
    rng = np.random.default_rng(seed)
    t = np.arange(int(seconds * FS)) / FS
    acc = np.stack([np.sin(2 * np.pi * cadence_hz * t + ph) + 0.4 * np.sin(2 * np.pi * 2 * cadence_hz * t)
                    + 0.05 * rng.normal(size=t.size) for ph in (0.0, 1.0, 2.0)], axis=1)
    f = hr_bpm / 60.0
    pulse = np.sin(2 * np.pi * f * t) + 0.3 * np.sin(2 * np.pi * 2 * f * t + 0.5)
    artifact = artifact_gain * (np.roll(acc[:, 0], 3) + 0.5 * np.roll(acc[:, 1], 7))
    ppg = np.stack([pulse + artifact + 0.2 * rng.normal(size=t.size),
                    pulse + 0.8 * artifact + 0.2 * rng.normal(size=t.size)], axis=1)
    return ppg, acc


def test_recovers_pulse_under_stronger_motion():
    ppg, acc = _recording(hr_bpm=80.0, artifact_gain=4.0)
    ups = track_wrist_hr(ppg, acc, FS)
    assert ups[0].t_end_s == pytest.approx(8.0)
    assert len(ups) == (60 - 8) // 2 + 1
    est = np.array([u.bpm for u in ups[3:]])           # skip canceller warm-up
    assert np.abs(est - 80.0).max() < 3.0


def test_pulse_at_the_motion_frequency_is_not_claimed_free():
    """Sanity: with HR far from the cadence the estimate stays on the pulse, not on the cadence (102 bpm)."""
    ppg, acc = _recording(hr_bpm=140.0, cadence_hz=1.7)
    est = np.array([u.bpm for u in track_wrist_hr(ppg, acc, FS)[3:]])
    assert np.abs(est - 140.0).max() < 3.0


def test_streaming_is_chunking_invariant():
    ppg, acc = _recording(seconds=30)
    whole = [u.bpm for u in track_wrist_hr(ppg, acc, FS)]
    m = MotionCompensatedHR(FS)
    chunked = []
    for s in range(0, len(ppg), 333):
        chunked += [u.bpm for u in m.push(ppg[s:s + 333], acc[s:s + 333])]
    assert chunked == whole


def test_confidence_is_a_probability_and_reset_restarts():
    ppg, acc = _recording(seconds=20)
    m = MotionCompensatedHR(FS)
    first = m.push(ppg, acc)
    assert all(0.0 <= u.confidence <= 1.0 for u in first)
    m.reset()
    assert [u.bpm for u in m.push(ppg, acc)] == [u.bpm for u in first]


def test_rejects_wrong_accelerometer_shape():
    with pytest.raises(ValueError):
        MotionCompensatedHR(FS).push(np.zeros((10, 2)), np.zeros((10, 2)))


def test_hr_range_sets_the_grid_and_the_default_floor_is_40():
    assert MotionCompensatedHR(FS).grid[0] == 40.0 and MotionCompensatedHR(FS).grid[-1] == 220.0
    assert MotionCompensatedHR(FS, hr_range=(30.0, 200.0)).grid[0] == 30.0
