"""Step counting from a wrist accelerometer at 25 Hz (the BMI270 idle rate).

Per 2 s segment, features are computed from a 4 s context (1 s of look-ahead) plus bout-level context up to
11 s each side: spectra summed over the three axes, periodicity, amplitude and jerk, all invariant to how the sensor is
rotated (the shipped model uses only rotation-invariant features; see ``segment_features``).
Two small gradient-boosted models decide the count: a classifier says whether the segment contains steps
(probability > 0.5), and a regressor trained on segments with steps gives how many. Totals are the sum over
segments, so steps appear with up to ~11 s of delay. Inference is plain NumPy over exported tree arrays
(:class:`TreeEnsemble`), so it can be ported to the phone.
"""

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from caseback_ppg.trees import TreeEnsemble
from scipy.signal import butter, resample_poly, sosfilt

FS = 25.0
SEG = 50            # 2 s
CTX = 100           # 4 s context
_NFFT = 256
_BINS = np.arange(0.5, 5.01, 0.25)
_SOS = butter(3, [0.5, 5.0], btype="bandpass", fs=FS, output="sos")
MODEL_PATH = Path(__file__).with_name("models") / "steps.json"


def _to_25(acc: np.ndarray, fs: float) -> np.ndarray:
    if fs == FS:
        return acc
    from math import gcd
    up, down = int(round(FS)), int(round(fs))
    g = gcd(up, down)
    return resample_poly(acc, up // g, down // g, axis=0)


def _windows(x: np.ndarray, n_seg: int) -> np.ndarray:
    """(n_seg, CTX, ...) context windows centred on each 2 s segment, edge-padded."""
    pad = (CTX - SEG) // 2
    p = np.pad(x, [(pad, pad + SEG)] + [(0, 0)] * (x.ndim - 1), mode="edge")
    idx = np.arange(n_seg)[:, None] * SEG + np.arange(CTX)[None, :]
    return p[idx]


def segment_features(acc: np.ndarray, fs: float = FS, *, orientation_free: bool = True) -> tuple[np.ndarray, list[str]]:
    """Feature matrix, one row per 2 s segment (the last partial segment is dropped).

    ``orientation_free`` (the default and what the shipped model uses) replaces the three features that depend on how
    the sensor sits on the wrist (per-axis std, per-axis gravity, per-axis jerk) by rotation-invariant ones: the sorted
    standard deviations of the band-passed motion along its principal axes, the norm of the gravity vector and the jerk
    of the vector norm. Everything else is already invariant (spectra summed over axes, autocorrelation and spread of
    the magnitude). ``orientation_free=False`` is the earlier per-axis set, kept to reproduce the comparison in
    tools/eval_steps.py; it needs the sensor mounted as in the training data (OxWalk, one fixed mounting).
    """
    acc = _to_25(np.asarray(acc, dtype=float), fs)
    n_seg = len(acc) // SEG
    if n_seg == 0:
        return np.zeros((0, 0)), []
    bp = sosfilt(_SOS, acc, axis=0)                        # per-axis band-pass, causal
    mag = np.linalg.norm(acc, axis=1)
    magbp = sosfilt(_SOS, mag - mag.mean())
    wa, wm = _windows(bp, n_seg), _windows(magbp, n_seg)
    wraw = _windows(acc, n_seg)

    win = np.hanning(CTX)[None, :, None]
    spec = (np.abs(np.fft.rfft(wa * win, _NFFT, axis=1)) ** 2).sum(axis=2)       # (n_seg, bins) summed over axes
    f = np.fft.rfftfreq(_NFFT, 1 / FS)
    band = (f >= 0.5) & (f <= 5.0)
    tot = spec[:, band].sum(axis=1) + 1e-12
    edges = np.digitize(f, _BINS)
    rel = np.stack([spec[:, (edges == k) & band].sum(axis=1) / tot for k in range(1, len(_BINS))], axis=1)
    fb = f[band]
    pk = spec[:, band].argmax(axis=1)
    dom_f, dom_rel = fb[pk], spec[:, band].max(axis=1) / tot

    m = wm - wm.mean(axis=1, keepdims=True)
    ac = np.fft.irfft(np.abs(np.fft.rfft(m, 256, axis=1)) ** 2, 256, axis=1)[:, :40]
    ac = ac / (ac[:, :1] + 1e-12)
    lo, hi = int(0.3 * FS), int(1.0 * FS)
    acf_max = ac[:, lo:hi].max(axis=1)
    acf_lag = (lo + ac[:, lo:hi].argmax(axis=1)) / FS
    lo2, hi2 = int(0.6 * FS), int(2.0 * FS)
    acf_stride = ac[:, lo2:hi2].max(axis=1)

    feats = {
        "log_power": np.log10(tot),
        "dom_f": dom_f, "dom_rel": dom_rel,
        "acf_max": acf_max, "acf_lag": acf_lag, "acf_stride": acf_stride,
        "mag_std": m.std(axis=1), "mag_range": np.ptp(m, axis=1),
    }
    if orientation_free:
        centred = wa - wa.mean(axis=1, keepdims=True)
        cov = np.einsum("nti,ntj->nij", centred, centred) / CTX
        e = np.sqrt(np.maximum(np.linalg.eigvalsh(cov), 0.0))[:, ::-1]
        feats.update({"jerk": np.linalg.norm(np.diff(wraw, axis=1), axis=2).mean(axis=1),
                      "pc_std_1": e[:, 0], "pc_std_2": e[:, 1], "pc_std_3": e[:, 2],
                      "g_norm": np.linalg.norm(wraw.mean(axis=1), axis=1)})
    else:
        feats.update({"jerk": np.abs(np.diff(wraw, axis=1)).sum(axis=2).mean(axis=1),
                      "ax_std_x": wa[:, :, 0].std(axis=1), "ax_std_y": wa[:, :, 1].std(axis=1),
                      "ax_std_z": wa[:, :, 2].std(axis=1),
                      "g_x": wraw[:, :, 0].mean(axis=1), "g_y": wraw[:, :, 1].mean(axis=1),
                      "g_z": wraw[:, :, 2].mean(axis=1)})
    names = list(feats) + [f"rel_{b:.2f}" for b in _BINS[:-1]]
    X = np.column_stack(list(feats.values()) + [rel])
    ctx_cols = [names.index(c) for c in ("log_power", "dom_f", "dom_rel", "acf_max", "acf_lag", "mag_std")]
    prev = np.vstack([X[:1, ctx_cols], X[:-1, ctx_cols]])
    nxt = np.vstack([X[1:, ctx_cols], X[-1:, ctx_cols]])
    prev2 = np.vstack([prev[:1], prev[:-1]])
    nxt2 = np.vstack([nxt[1:], nxt[-1:]])
    names += [f"{names[c]}@{s}" for s, c in [(s, c) for s in ("-1", "+1", "-2", "+2") for c in ctx_cols]]
    # bout-level context: mean over +-5 segments (11 s each side) of periodicity and effort
    roll_cols = [names.index(c) for c in ("log_power", "dom_rel", "acf_max", "mag_std", "jerk", "acf_stride")]
    roll = _rolling_mean(X[:, roll_cols], 5)
    roll_f = _rolling_mean(X[:, [names.index("dom_f")]], 5)
    names += [f"{names[c]}~11" for c in roll_cols] + ["dom_f~11"]
    return np.hstack([X, prev, nxt, prev2, nxt2, roll, roll_f]), names


def _rolling_mean(x: np.ndarray, half: int) -> np.ndarray:
    k = 2 * half + 1
    p = np.pad(x, [(half, half), (0, 0)], mode="edge")
    c = np.cumsum(np.vstack([np.zeros((1, x.shape[1])), p]), axis=0)
    return (c[k:] - c[:-k]) / k


def segment_labels(step_samples: np.ndarray, n_samples: int, fs: float = FS) -> np.ndarray:
    """Annotated steps per 2 s segment (aligned with :func:`segment_features` at 25 Hz)."""
    idx = np.round(np.asarray(step_samples) * FS / fs).astype(int)
    n_seg = int(n_samples * FS / fs) // SEG
    return np.bincount(idx[idx < n_seg * SEG] // SEG, minlength=n_seg).astype(float)


@dataclass(frozen=True)
class StepModel:
    gate: TreeEnsemble       # log-odds that the segment contains steps
    count: TreeEnsemble      # steps in a segment that has some
    threshold: float = 0.5
    orientation_free: bool = True       # features it was trained on: see :func:`segment_features`

    def predict(self, X: np.ndarray) -> np.ndarray:
        p = 1.0 / (1.0 + np.exp(-self.gate.predict(X)))
        return np.where(p > self.threshold, np.maximum(self.count.predict(X), 0.0), 0.0)

    def to_json(self) -> str:
        return json.dumps({"gate": json.loads(self.gate.to_json()), "count": json.loads(self.count.to_json()),
                           "threshold": self.threshold,
                           "orientation_free": self.orientation_free})

    @classmethod
    def from_json(cls, text: str) -> "StepModel":
        d = json.loads(text)
        return cls(TreeEnsemble.from_json(json.dumps(d["gate"])), TreeEnsemble.from_json(json.dumps(d["count"])),
                   d["threshold"], d.get("orientation_free", False))


def load_model(path: Path = MODEL_PATH) -> StepModel:
    return StepModel.from_json(path.read_text())


def count_steps(acc: np.ndarray, fs: float = FS, model: StepModel | None = None) -> np.ndarray:
    """Predicted steps per 2 s segment (float, >= 0). Sum for a total."""
    model = model or load_model()
    X, _ = segment_features(acc, fs, orientation_free=model.orientation_free)
    return model.predict(X) if len(X) else np.zeros(0)
