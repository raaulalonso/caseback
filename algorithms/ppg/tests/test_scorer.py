import numpy as np
import pytest

from caseback_ppg import MotionCompensatedHR
from caseback_ppg.scorer import FEATURES, CandidateScorer, candidates, features
from caseback_ppg.wrist import WindowSpectra
from test_wrist import _recording

G = np.arange(40, 221, 1.0)


def _spectra(peaks, acc_peak=100.0):
    def bump(f, w=3.0):
        return np.exp(-0.5 * ((G - f) / w) ** 2)
    c = sum(a * bump(f) for f, a in peaks)
    return WindowSpectra(G, c / c.max(), c / c.max(), bump(acc_peak) / 1.0, 0.1)


def test_candidates_and_features_shapes():
    ws = _spectra([(80, 1.0), (160, 0.4), (110, 0.7)])
    idx = candidates(ws)
    assert {80, 110, 160} <= {int(G[i]) for i in idx}
    X = features(ws, idx)
    assert X.shape == (len(idx), len(FEATURES)) and np.isfinite(X).all()


def test_scorer_returns_positive_emission_over_grid():
    sc = CandidateScorer.load()
    e = sc(_spectra([(80, 1.0), (160, 0.4)]))
    assert e.shape == G.shape and (e > 0).all()


def test_learned_tracker_follows_the_pulse_at_two_sample_rates():
    for hr, fs in ((80.0, 125.0), (140.0, 125.0)):
        ppg, acc = _recording(hr_bpm=hr)
        est = np.array([u.bpm for u in MotionCompensatedHR.learned(fs).push(ppg, acc)[3:]])
        assert np.median(np.abs(est - hr)) < 4.0


def test_learned_tracker_is_chunking_invariant():
    ppg, acc = _recording(seconds=30)
    whole = [u.bpm for u in MotionCompensatedHR.learned().push(ppg, acc)]
    m = MotionCompensatedHR.learned()
    chunked = []
    for s in range(0, len(ppg), 401):
        chunked += [u.bpm for u in m.push(ppg[s:s + 401], acc[s:s + 401])]
    assert chunked == whole
