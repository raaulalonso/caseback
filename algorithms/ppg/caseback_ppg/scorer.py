"""Learned candidate scorer for the wrist tracker.

The spectrum of a motion-corrupted PPG window has several peaks: the pulse, motion, and their harmonics or
subharmonics. For each candidate peak this scores "is this the pulse?" from how it relates to the other peaks:
its power before and after motion cancellation, the accelerometer power at f, f/2, 2f and 3f/2, the PPG power
at those same ratios, its rank and its distance to the dominant accelerometer peak. A gradient-boosted classifier
(:class:`caseback_ppg.trees.TreeEnsemble`) trained on labelled windows turns those into a probability, and
:class:`CandidateScorer` returns it as an emission over the bpm grid for the tracker's HMM.

Trained on IEEE SPC 2015 TRAIN and PPG-DaLiA TRAIN only (tools/train_scorer.py).
"""

import json
from pathlib import Path

import numpy as np
from scipy.signal import find_peaks

from .trees import TreeEnsemble
from .wrist import WindowSpectra

MODEL_PATH = Path(__file__).with_name("models") / "scorer.json"
N_CANCELLED, N_RAW = 6, 3
FEATURES = ["f", "c", "c_rank", "c_rel", "r", "r_rel", "c_over_r", "a", "a_half", "a_double", "a_3half",
            "c_half", "c_double", "c_3half", "c_2third", "df_acc", "df_acc2", "df_acc_half", "acc_std",
            "acc_total", "n_peaks", "c_second_rel"]


def _at(spec: np.ndarray, grid: np.ndarray, f: float) -> float:
    """Local maximum of ``spec`` within +-2 bpm of frequency ``f`` (0 outside the grid)."""
    if f < grid[0] or f > grid[-1]:
        return 0.0
    i = int(round(f - grid[0]))
    return float(spec[max(i - 2, 0):i + 3].max())


def candidates(ws: WindowSpectra) -> np.ndarray:
    """Grid indices of candidate peaks: strongest of the cancelled spectrum plus a few of the raw one."""
    idx: list[int] = []
    for spec, n in ((ws.cancelled, N_CANCELLED), (ws.raw, N_RAW)):
        pk, prop = find_peaks(spec, height=0.05)
        if len(pk) == 0:
            pk = np.array([int(spec.argmax())])
            prop = {"peak_heights": spec[pk]}
        for i in pk[np.argsort(prop["peak_heights"])[::-1][:n]]:
            if all(abs(i - j) > 2 for j in idx):
                idx.append(int(i))
    return np.array(sorted(idx))


def features(ws: WindowSpectra, idx: np.ndarray) -> np.ndarray:
    g, c, r, a = ws.grid, ws.cancelled, ws.raw, ws.acc
    f_acc = g[int(a.argmax())]
    order = np.argsort(-c[idx])
    rank = np.empty(len(idx)); rank[order] = np.arange(len(idx))
    top = np.sort(c[idx])[::-1]
    second = top[1] if len(top) > 1 else 0.0
    rows = []
    for k, i in enumerate(idx):
        f = g[i]
        rows.append([f, c[i], rank[k], c[i] / max(c.max(), 1e-12), r[i], r[i] / max(r.max(), 1e-12),
                     c[i] / (r[i] + 1e-3), _at(a, g, f), _at(a, g, f / 2), _at(a, g, 2 * f), _at(a, g, 1.5 * f),
                     _at(c, g, f / 2), _at(c, g, 2 * f), _at(c, g, 1.5 * f), _at(c, g, 2 * f / 3),
                     abs(f - f_acc), abs(f - 2 * f_acc), abs(f - f_acc / 2), ws.acc_std,
                     float(np.log10(a.sum() + 1e-9)), float(len(idx)), second])
    return np.array(rows)


class CandidateScorer:
    """Callable ``WindowSpectra -> emission over the grid``: candidate probabilities smeared by ``width_bpm``."""

    def __init__(self, model: TreeEnsemble, width_bpm: float = 2.0, floor: float = 0.1):
        self.model, self.width, self.floor = model, width_bpm, floor

    def __call__(self, ws: WindowSpectra) -> np.ndarray:
        idx = candidates(ws)
        p = 1.0 / (1.0 + np.exp(-self.model.predict(features(ws, idx))))
        out = np.full(len(ws.grid), self.floor)
        for i, pk in zip(idx, p):
            out += pk * np.exp(-0.5 * ((ws.grid - ws.grid[i]) / self.width) ** 2)
        return out

    @classmethod
    def load(cls, path: Path = MODEL_PATH) -> "CandidateScorer":
        d = json.loads(path.read_text())
        return cls(TreeEnsemble.from_json(json.dumps(d["model"])), d["width_bpm"], d["floor"])

    def save(self, path: Path = MODEL_PATH) -> None:
        path.parent.mkdir(exist_ok=True)
        path.write_text(json.dumps({"model": json.loads(self.model.to_json()), "width_bpm": self.width,
                                    "floor": self.floor, "features": FEATURES}))
