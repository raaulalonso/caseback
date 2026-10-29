import numpy as np
import pytest

from caseback_wellness import steps
from caseback_wellness.datasets import oxwalk

FS = 25.0


def _walk(seconds=60, step_hz=1.9, seed=0):
    """Wrist-like walking: arm swing at the stride frequency, vertical bounce at the step frequency."""
    rng = np.random.default_rng(seed)
    t = np.arange(int(seconds * FS)) / FS
    acc = np.stack([0.5 * np.sin(2 * np.pi * step_hz / 2 * t),
                    0.3 * np.sin(2 * np.pi * step_hz / 2 * t + 1.0) + 0.1,
                    1.0 + 0.35 * np.sin(2 * np.pi * step_hz * t) + 0.1 * np.sin(4 * np.pi * step_hz * t)], axis=1)
    return acc + 0.03 * rng.normal(size=acc.shape)


def test_features_shape_and_finite():
    X, names = steps.segment_features(_walk(60))
    assert X.shape == (30, len(names)) and np.isfinite(X).all()
    assert steps.segment_features(np.zeros((10, 3)))[0].shape[0] == 0


def _random_rotation(seed):
    q, r = np.linalg.qr(np.random.default_rng(seed).normal(size=(3, 3)))
    q = q * np.sign(np.diag(r))
    return q if np.linalg.det(q) > 0 else q * np.array([1, 1, -1])


def test_orientation_free_features_do_not_change_under_rotation_but_the_per_axis_ones_do():
    acc = _walk(60)
    for seed in range(3):
        rot = acc @ _random_rotation(seed).T
        a, names = steps.segment_features(acc, orientation_free=True)
        b, _ = steps.segment_features(rot, orientation_free=True)
        assert a.shape == b.shape and np.isfinite(a).all() and a == pytest.approx(b, rel=1e-6, abs=1e-6)
    a, names = steps.segment_features(acc, orientation_free=False)
    b, _ = steps.segment_features(acc @ _random_rotation(0).T, orientation_free=False)
    assert not np.allclose(a, b, atol=1e-3) and "g_x" in names and "g_norm" not in names


def test_step_model_json_keeps_the_feature_set_and_old_files_default_to_per_axis():
    import json
    m = steps.load_model()
    assert m.orientation_free is True and steps.StepModel.from_json(m.to_json()).orientation_free is True
    old = json.loads(m.to_json()); del old["orientation_free"]
    assert steps.StepModel.from_json(json.dumps(old)).orientation_free is False


def test_labels_align_with_segments():
    y = steps.segment_labels(np.array([0, 10, 49, 50, 120]), 250)
    assert list(y) == [3, 1, 1, 0, 0]


def test_tree_ensemble_matches_sklearn_and_roundtrips():
    from sklearn.ensemble import GradientBoostingClassifier, GradientBoostingRegressor
    rng = np.random.default_rng(1)
    X = rng.normal(size=(400, 5)); y = 2 * X[:, 0] + np.sin(X[:, 1]) + 0.1 * rng.normal(size=400)
    reg = GradientBoostingRegressor(n_estimators=20, max_depth=3, random_state=0).fit(X, y)
    te = steps.TreeEnsemble.from_sklearn(reg)
    assert te.predict(X) == pytest.approx(reg.predict(X), abs=1e-9)
    assert steps.TreeEnsemble.from_json(te.to_json()).predict(X) == pytest.approx(te.predict(X))
    clf = GradientBoostingClassifier(n_estimators=20, max_depth=3, random_state=0).fit(X, (y > 0).astype(int))
    raw = steps.TreeEnsemble.from_sklearn(clf).predict(X)
    assert 1 / (1 + np.exp(-raw)) == pytest.approx(clf.predict_proba(X)[:, 1], abs=1e-9)


def test_shipped_model_gives_the_same_count_whatever_the_mounting():
    acc = _walk(120)
    base = steps.count_steps(acc).sum()
    for seed in range(3):
        assert steps.count_steps(acc @ _random_rotation(seed).T).sum() == pytest.approx(base, rel=1e-4)


def test_shipped_model_counts_walking_and_ignores_stillness():
    walking = steps.count_steps(_walk(120)).sum()
    assert 0.6 * 228 <= walking <= 1.4 * 228            # 1.9 steps/s for 120 s
    rng = np.random.default_rng(2)
    still = np.array([0.0, 0.0, 1.0]) + 0.01 * rng.normal(size=(int(120 * FS), 3))
    assert steps.count_steps(still).sum() < 5


def test_other_sample_rates_are_resampled():
    t = np.arange(int(60 * 50)) / 50
    walk50 = np.stack([0.5 * np.sin(2 * np.pi * .95 * t), 0.3 * np.sin(2 * np.pi * .95 * t + 1) + .1,
                       1 + 0.35 * np.sin(2 * np.pi * 1.9 * t)], axis=1)
    assert steps.count_steps(walk50, 50.0).sum() > 60


@pytest.mark.dataset
@pytest.mark.skipif(not oxwalk.available(), reason="OxWalk not downloaded")
def test_oxwalk_loader():
    r = oxwalk.load(3)
    assert r.fs == 25.0 and r.acc.shape[1] == 3 and len(r.step_samples) == 4144
