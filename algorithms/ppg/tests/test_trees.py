import numpy as np
import pytest
from sklearn.ensemble import GradientBoostingClassifier

from caseback_ppg.trees import MulticlassEnsemble


def test_multiclass_matches_sklearn_and_roundtrips():
    rng = np.random.default_rng(0)
    X = rng.normal(size=(600, 4))
    y = np.digitize(X[:, 0] + 0.5 * X[:, 1] + 0.2 * rng.normal(size=600), [-0.5, 0.5])   # 3 classes
    gbc = GradientBoostingClassifier(n_estimators=15, max_depth=3, random_state=0).fit(X, y)
    m = MulticlassEnsemble.from_sklearn(gbc)
    assert m.predict_proba(X) == pytest.approx(gbc.predict_proba(X), abs=1e-9)
    assert MulticlassEnsemble.from_json(m.to_json()).predict_proba(X) == pytest.approx(m.predict_proba(X))
