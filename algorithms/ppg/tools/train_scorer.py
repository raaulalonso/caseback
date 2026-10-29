"""Train the candidate scorer used by MotionCompensatedHR.learned().

    python tools/train_scorer.py [--save]        (needs: pip install -e ".[train]")

Data: IEEE SPC 2015 TRAIN (12 recordings) and PPG-DaLiA TRAIN (10 recordings) only; both TEST splits are never
read here. Windows are streamed through the unchanged front end (NLMS canceller, spectra), candidate peaks are
extracted, and the nearest candidate within 5 bpm of the chest-ECG label is the positive one. IEEE rows get weight 8
so the 12 running recordings are not drowned by the 43 000 DaLiA windows (a choice, not tuned).
Reports recording-grouped 5-fold cross-validation (held-out recordings) of the full pipeline, then fits on all TRAIN.
"""

import argparse

import numpy as np
from joblib import Parallel, delayed
from sklearn.ensemble import GradientBoostingClassifier

from caseback_ppg import MotionCompensatedHR
from caseback_ppg.datasets import ieeeppg, ppgdalia
from caseback_ppg.scorer import MODEL_PATH, CandidateScorer, candidates, features
from caseback_ppg.trees import TreeEnsemble

TOL_BPM, W_IEEE = 5.0, 8.0
PARAMS = dict(n_estimators=150, max_depth=4, learning_rate=0.08, subsample=0.7, min_samples_leaf=30, random_state=0)
GRID = np.arange(40, 221, 1.0)


def collect(kind: str, split: str, s: int, w, ids) -> dict:
    if kind == "dalia":
        ppg, acc, ref = ppgdalia.stream(w, ids, s); fs = ppgdalia.FS
    else:
        ppg, acc, ref = ieeeppg.stream(w, ids, s); fs = ieeeppg.FS
    store: list = []
    MotionCompensatedHR(fs, taps=round(0.384 * fs), on_spectrum=store.append).push(ppg, acc)
    rows, win = [], []
    for i, ws in enumerate(store):
        f = features(ws, candidates(ws))
        rows.append(f); win.append(np.full(len(f), i))
    X, win = np.vstack(rows), np.concatenate(win)
    y = np.zeros(len(X), int)
    for i, r in enumerate(ref):
        m = np.flatnonzero(win == i)
        d = np.abs(X[m, 0] - r)
        if d.min() <= TOL_BPM:
            y[m[d.argmin()]] = 1
    return dict(kind=kind, X=X, y=y, win=win, ref=ref, w=np.full(len(y), W_IEEE if kind == "ieee" else 1.0))


def hmm(E: np.ndarray, sigma: float = 2.0) -> np.ndarray:
    K = np.exp(-np.abs(GRID[:, None] - GRID[None, :]) / sigma); K /= K.sum(0, keepdims=True)
    est, a = np.zeros(len(E)), None
    for i, e in enumerate(E):
        a = e / e.sum() if a is None else e * (K @ a)
        a /= a.sum(); est[i] = GRID[a.argmax()]
    return est


def emission(r: dict, p: np.ndarray, width: float = 2.0, floor: float = 0.1) -> np.ndarray:
    E = np.full((len(r["ref"]), len(GRID)), floor)
    for pk, fk, w in zip(p, r["X"][:, 0], r["win"]):
        E[w] += pk * np.exp(-0.5 * ((GRID - fk) / width) ** 2)
    return E


def fit(recs: list[dict]) -> GradientBoostingClassifier:
    return GradientBoostingClassifier(**PARAMS).fit(
        np.vstack([r["X"] for r in recs]), np.concatenate([r["y"] for r in recs]),
        sample_weight=np.concatenate([r["w"] for r in recs]))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--save", action="store_true")
    args = ap.parse_args()
    recs: list[dict] = []
    for kind, mod in (("dalia", ppgdalia), ("ieee", ieeeppg)):
        w = mod.load("TRAIN")
        ids = mod.recording_ids(w) if kind == "dalia" else mod.subject_ids(w)
        recs += Parallel(n_jobs=-1)(delayed(collect)(kind, "TRAIN", s, w, ids) for s in range(ids.max() + 1))
        print(f"{kind}: {ids.max() + 1} training recordings", flush=True)

    order = np.random.default_rng(0).permutation(len(recs))
    folds = [order[i::5] for i in range(5)]

    def run(fo):
        m = fit([recs[i] for i in range(len(recs)) if i not in set(fo)])
        return {i: m.predict_proba(recs[i]["X"])[:, 1] for i in fo}
    oof: dict = {}
    for d in Parallel(n_jobs=5)(delayed(run)(fo) for fo in folds):
        oof.update(d)
    print("\nRecording-grouped 5-fold CV on TRAIN (each recording predicted by a model that never saw it):")
    for kind in ("dalia", "ieee"):
        e = np.concatenate([np.abs(hmm(emission(r, oof[i])) - r["ref"]) for i, r in enumerate(recs) if r["kind"] == kind])
        print(f"  {kind:6s} MAE {e.mean():5.2f}  median {np.median(e):5.2f}  <=5 bpm {np.mean(e <= 5):6.1%}")

    if args.save:
        CandidateScorer(TreeEnsemble.from_sklearn(fit(recs))).save()
        print(f"\nsaved {MODEL_PATH} ({MODEL_PATH.stat().st_size / 1e3:.0f} kB)")


if __name__ == "__main__":
    main()
