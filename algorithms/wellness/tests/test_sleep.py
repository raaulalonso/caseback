import numpy as np
import pytest

from caseback_wellness import sleep
from caseback_wellness.datasets import sleepaccel


def _night(hours=2.0, seed=0):
    rng = np.random.default_rng(seed)
    n = int(hours * 3600 * 50)
    t = np.sort(rng.uniform(0, hours * 3600, n))
    acc = np.array([0.0, 0.0, -1.0]) + 0.002 * rng.normal(size=(n, 3))
    acc[(t > 3600) & (t < 3660)] += 0.3 * rng.normal(size=((t > 3600) & (t < 3660)).sum())[:, None]   # one restless minute
    ht = np.arange(0, hours * 3600, 5.0)
    hr = 58 + rng.normal(size=ht.size)
    hr[100] = 141                                                                                  # spurious spike
    return t, acc, ht, hr


def test_clean_hr_drops_spikes_and_impossible_values():
    t, hr = np.arange(0, 600, 5.0), np.full(120, 60.0)
    hr[50], hr[60] = 141.0, 20.0
    ct, ch = sleep.clean_hr(t, hr)
    assert len(ch) == 118 and ch.max() < 100 and ch.min() > 50


def test_epoch_features_shape_and_movement_detected():
    t, acc, ht, hr = _night()
    n_ep = int(2 * 3600 / 30)
    X, names = sleep.epoch_features(t, acc, ht, hr, n_ep)
    assert X.shape == (n_ep, len(names)) and np.isfinite(X).all()
    act = X[:, names.index("act")]
    assert act[120:122].min() > 5 * np.median(act)          # epochs 120-121 hold the restless minute


def test_smoother_sums_to_one_and_removes_isolated_blip():
    T = np.array([[.9, .1, 0, 0], [.02, .96, .01, .01], [0, .1, .9, 0], [.02, .06, 0, .92]])
    prior = np.array([.1, .55, .15, .2])
    proba = np.tile([.02, .9, .04, .04], (40, 1)); proba[20] = [.6, .3, .05, .05]     # one uncertain wake epoch
    post = sleep.smooth_stages(proba, T, prior, 1.0)
    assert post.sum(axis=1) == pytest.approx(1.0)
    assert (post.argmax(axis=1) == 1).all() and (proba.argmax(axis=1) == 0)[20]


def test_transition_matrix_rows_sum_to_one_and_ignore_unscored():
    T = sleep.transition_matrix([np.array([0, 0, 1, 1, -1, 1, 2, 2, 3])])
    assert T.sum(axis=1) == pytest.approx(1.0) and T.shape == (4, 4)


def test_detect_sleep_window_finds_the_night_in_a_day_of_activity():
    rng = np.random.default_rng(0)
    n = 24 * 120                                                # one day of 30 s epochs, starting at 08:00
    act = 0.05 + 0.03 * rng.random(n)                           # awake: busy
    night = slice(15 * 120, 23 * 120)                           # 23:00 - 07:00
    act[night] = 0.004 + 0.001 * rng.random(8 * 120)
    act[night.start + 200:night.start + 210] = 0.06             # a few restless epochs inside the night
    win = sleep.detect_sleep_window(act)
    assert win is not None
    assert abs(win[0] - night.start) < 30 and abs(win[1] - (night.stop - 1)) < 30
    assert sleep.detect_sleep_window(0.05 + 0.03 * rng.random(n)) is None       # a day with no long still stretch
    assert sleep.detect_sleep_window(act[:100]) is None


def test_summary_and_score():
    stages = np.r_[np.zeros(10), np.ones(600), np.full(90, 2), np.full(120, 3), np.zeros(20)].astype(int)
    sm = sleep.summarise(stages)
    assert sm.total_sleep_min == pytest.approx(405.0) and sm.onset_latency_min == pytest.approx(5.0)
    assert sm.waso_min == pytest.approx(0.0) and 0 < sm.efficiency < 1
    assert 60 < sleep.sleep_score(sm) <= 100
    assert sleep.sleep_score(sleep.summarise(np.zeros(100, int))) == 0.0
    assert sleep.sleep_score(sleep.summarise(np.ones(100, int))) < sleep.sleep_score(sm)     # 50 min of sleep vs a full night


def test_shipped_model_stages_a_synthetic_night():
    t, acc, ht, hr = _night()
    n_ep = int(2 * 3600 / 30)
    X, _ = sleep.epoch_features(t, acc, ht, hr, n_ep)
    stages, post = sleep.SleepModel.load().stage(X)
    assert stages.shape == (n_ep,) and post.shape == (n_ep, 4) and post.sum(axis=1) == pytest.approx(1.0)


@pytest.mark.dataset
@pytest.mark.skipif(not sleepaccel.available(), reason="Walch sleep dataset not downloaded")
def test_walch_loader():
    subs = sleepaccel.subjects()
    n = sleepaccel.load(subs[0])
    assert len(subs) == 31 and n.acc.shape[1] == 3 and set(np.unique(n.stages)) <= {-1, 0, 1, 2, 3}


def test_uniform_grid_interpolates_short_gaps_and_leaves_long_ones_missing():
    t = np.r_[np.arange(0, 100, 0.04), np.arange(120, 400, 0.04), np.arange(500, 600, 0.04)]      # 20 s and 100 s holes
    acc = np.tile([0.0, 0.0, -1.0], (len(t), 1))
    _, g = sleep.to_uniform_25hz(t, acc, n_epochs=20)                                              # 600 s
    at = lambda s: g[int(s * sleep.ACC_FS)]                                                        # noqa: E731
    assert at(110)[2] == pytest.approx(-1.0)                    # 20 s hole: interpolated
    assert np.isnan(at(450)).all() and np.isnan(at(499)).all()  # 100 s hole: left missing
    assert np.isfinite(at(50)).all() and np.isfinite(at(550)).all()
    _, g2 = sleep.to_uniform_25hz(t, acc, n_epochs=20, max_gap_s=200.0)
    assert np.isfinite(g2).all()


def test_gaps_at_the_ends_are_missing_and_an_empty_recording_is_all_missing():
    t = np.arange(300, 600, 0.04)
    _, g = sleep.to_uniform_25hz(t, np.tile([0.0, 0.0, -1.0], (len(t), 1)), n_epochs=20)
    assert np.isnan(g[: int(200 * sleep.ACC_FS)]).all() and np.isfinite(g[int(300 * sleep.ACC_FS):]).all()
    _, e = sleep.to_uniform_25hz(np.zeros(0), np.zeros((0, 3)), n_epochs=4)
    assert np.isnan(e).all()


def test_epoch_features_tolerate_a_data_gap_and_report_coverage():
    t, acc, ht, hr = _night()
    keep = (t < 3000) | (t > 3600)                               # 10 minute hole in the accelerometer
    n_ep = int(2 * 3600 / 30)
    X, names = sleep.epoch_features(t[keep], acc[keep], ht, hr, n_ep)
    assert X.shape == (n_ep, len(names)) and np.isfinite(X).all()
    cov = sleep.epoch_coverage(t[keep], acc[keep], n_ep)
    assert cov[110:118].max() == 0.0 and cov[:90].min() > 0.99 and cov[125:].min() > 0.99
    assert X[110:118, names.index("act")].max() == 0.0          # filled with 0, flagged by coverage rather than invented
    X0, _ = sleep.epoch_features(t, acc, ht, hr, n_ep)
    own = [names.index(c) for c in ("act", "jerk_max", "mag_std", "bursts", "tilt")]      # per-epoch, no context
    assert np.allclose(X0[:99][:, own], X[:99][:, own]) and np.isfinite(X0).all()


def test_smoother_bridges_invalid_epochs_with_the_chain():
    T = np.array([[.9, .1, 0, 0], [.02, .96, .01, .01], [0, .1, .9, 0], [.02, .06, 0, .92]])
    prior = np.array([.1, .55, .15, .2])
    proba = np.tile([.02, .04, .9, .04], (30, 1)); proba[10:20] = [.9, .03, .03, .04]           # garbage where invalid
    valid = np.ones(30, bool); valid[10:20] = False
    post = sleep.smooth_stages(proba, T, prior, 1.0, valid=valid)
    assert post.sum(axis=1) == pytest.approx(1.0)
    assert (post.argmax(axis=1)[10:20] == 2).all()                # deep sleep on both sides carries across the gap
    assert (sleep.smooth_stages(proba, T, prior, 1.0).argmax(axis=1)[12:18] == 0).all()
