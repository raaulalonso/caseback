"""Gradient-boosted trees as flat arrays, evaluated with plain NumPy (no scikit-learn at inference time).

Fit with scikit-learn offline, export with :meth:`TreeEnsemble.from_sklearn`, ship the JSON. Small enough to
port to Swift: each tree is five arrays and prediction is a loop over nodes.
"""

import json
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class TreeEnsemble:
    """Gradient-boosted regression trees stored as flat arrays (sklearn export), evaluated with NumPy."""
    init: float
    lr: float
    trees: tuple                                   # each: (left, right, feature, threshold, value) arrays

    @classmethod
    def from_sklearn(cls, gbr) -> "TreeEnsemble":
        """From a fitted GradientBoostingRegressor or (binary) GradientBoostingClassifier (raw log-odds output)."""
        trees = []
        for est in gbr.estimators_[:, 0]:
            t = est.tree_
            trees.append((t.children_left.copy(), t.children_right.copy(), t.feature.copy(),
                          t.threshold.copy(), t.value[:, 0, 0].copy()))
        init = gbr.init_
        if hasattr(init, "class_prior_"):                          # classifier: prior log-odds
            p1 = float(init.class_prior_[1])
            base = float(np.log(p1 / (1.0 - p1)))
        else:
            base = float(init.constant_[0][0])
        return cls(base, float(gbr.learning_rate), tuple(trees))

    def predict(self, X: np.ndarray) -> np.ndarray:
        X = np.asarray(X, dtype=float)
        out = np.full(len(X), self.init)
        rows = np.arange(len(X))
        for left, right, feat, thr, val in self.trees:
            node = np.zeros(len(X), dtype=int)
            while True:
                internal = left[node] != -1
                if not internal.any():
                    break
                go_left = X[rows, np.maximum(feat[node], 0)] <= thr[node]
                node = np.where(internal, np.where(go_left, left[node], right[node]), node)
            out += self.lr * val[node]
        return out

    def to_json(self) -> str:
        return json.dumps({"init": self.init, "lr": self.lr, "trees": [[a.tolist() for a in t] for t in self.trees]})

    @classmethod
    def from_json(cls, text: str) -> "TreeEnsemble":
        d = json.loads(text)
        return cls(d["init"], d["lr"], tuple((np.array(t[0]), np.array(t[1]), np.array(t[2]), np.array(t[3]),
                                                np.array(t[4])) for t in d["trees"]))


@dataclass(frozen=True)
class MulticlassEnsemble:
    """Softmax over one :class:`TreeEnsemble` per class (sklearn GradientBoostingClassifier with > 2 classes)."""
    classes: tuple
    members: tuple

    @classmethod
    def from_sklearn(cls, gbc) -> "MulticlassEnsemble":
        prior = gbc.init_.class_prior_
        members = []
        for k in range(len(gbc.classes_)):
            trees = []
            for est in gbc.estimators_[:, k]:
                t = est.tree_
                trees.append((t.children_left.copy(), t.children_right.copy(), t.feature.copy(),
                              t.threshold.copy(), t.value[:, 0, 0].copy()))
            members.append(TreeEnsemble(float(np.log(prior[k])), float(gbc.learning_rate), tuple(trees)))
        return cls(tuple(int(c) for c in gbc.classes_), tuple(members))

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        raw = np.column_stack([m.predict(X) for m in self.members])
        raw -= raw.max(axis=1, keepdims=True)
        p = np.exp(raw)
        return p / p.sum(axis=1, keepdims=True)

    def to_json(self) -> str:
        return json.dumps({"classes": list(self.classes),
                           "members": [json.loads(m.to_json()) for m in self.members]})

    @classmethod
    def from_json(cls, text: str) -> "MulticlassEnsemble":
        d = json.loads(text)
        return cls(tuple(d["classes"]), tuple(TreeEnsemble.from_json(json.dumps(m)) for m in d["members"]))
